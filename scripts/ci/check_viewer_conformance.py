#!/usr/bin/env python3
"""Check every report viewer against docs/plugin-authoring/references/report-viewer-standard.md.

Only the mechanically decidable rules live here. R2 (no number printed twice) and
R3 (an actionable number must not look inert) are editorial and are deliberately
NOT checked -- a lint that pretends to decide them would report success on prose it
cannot read, which is the failure mode CLAUDE.md catalogues.

Every content check runs against the document with its <style> blocks REMOVED.
That is not cosmetic: confab defines `.legend`/`.legend .swatch` and uses neither,
so a naive substring search for "legend" passes on a viewer that has none. The same
defence is why test/docs/docs_ux_audit.py strips comments before grepping.

Exits 1 and names every violation. Never exits 0 on an unreadable file.
"""

from __future__ import annotations

import os
import re
import struct
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CANONICAL_MARKER = "<!--__DESIGN_TOKENS__-->"
VARIANT_MARKERS = ("/*__DESIGN_TOKENS__*/", "/*__TOKENS__*/")
STYLE_RE = re.compile(r"<style\b.*?</style>", re.DOTALL | re.IGNORECASE)
BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
HTML_COMMENT_RE = re.compile(r"<!--(?!__).*?-->", re.DOTALL)
# `//` only when it is not the tail of a scheme (http://), so a URL survives.
LINE_COMMENT_RE = re.compile(r"(?<!:)//[^\n]*")
SCRIPT_RE = re.compile(r"<script\b.*?</script>", re.DOTALL | re.IGNORECASE)


def class_token_re(token: str) -> re.Pattern:
    """An OPENING TAG whose class attribute contains `token` as a whole word.

    Not a substring search for the token anywhere in the file. `renderLegend()`
    in a script, or the word "legend" in a comment, satisfied the old check --
    so a viewer could delete its legend element, keep a dead helper, and stay
    green. Same for class="verdict" quoted inside a script string.
    """
    return re.compile(
        r"<[a-zA-Z][^>]*\bclass\s*=\s*[\"\']([^\"\']*\s)?" + token + r"(\s[^\"\']*)?[\"\']",
        re.IGNORECASE,
    )


VERDICT_RE = class_token_re("verdict")
LEGEND_RE = class_token_re("legend")
NOTE_RE = class_token_re("note")
TITLE_RE = re.compile(r"<title>(.*?)</title>", re.DOTALL | re.IGNORECASE)
# U+2014 EM DASH. Written as an escape so a mangled encoding cannot silently
# turn this into a pattern that matches nothing.
TITLE_SHAPE = re.compile(r"^([a-z0-9-]+) — .+$")


def jpeg_size(path: str) -> tuple[int, int]:
    """Width/height from the JPEG SOF marker. No third-party dependency.

    Raises rather than returning a sentinel: a screenshot whose header cannot be
    parsed must fail the run, not silently pass a dimension check.
    """
    with open(path, "rb") as fh:
        if fh.read(2) != b"\xff\xd8":
            raise ValueError(f"{path}: not a JPEG")
        while True:
            byte = fh.read(1)
            while byte and byte != b"\xff":
                byte = fh.read(1)
            marker = fh.read(1)
            while marker == b"\xff":
                marker = fh.read(1)
            if not marker:
                raise ValueError(f"{path}: no SOF marker found")
            # SOF0-SOF15, excluding the non-frame markers DHT/JPG/DAC.
            if 0xC0 <= marker[0] <= 0xCF and marker[0] not in (0xC4, 0xC8, 0xCC):
                fh.read(3)
                height, width = struct.unpack(">HH", fh.read(4))
                return width, height
            (length,) = struct.unpack(">H", fh.read(2))
            fh.read(length - 2)


def strip_comments(text: str) -> str:
    """Remove comments before any literal search.

    Written after this lint flagged its own remediation: the comment explaining
    why the bare `61px` literal was replaced by a token itself contains the
    string `61px`, so a raw substring search reported a violation in a file that
    had none. A guard that cannot tell code from the prose about the code is the
    same defect test/docs/docs_ux_audit.py's js_code() helper exists to avoid.

    The HTML pattern deliberately spares `<!--__...__-->` injection markers --
    those ARE checked, and stripping them would make S2 unfalsifiable.
    """
    text = BLOCK_COMMENT_RE.sub(" ", text)
    text = HTML_COMMENT_RE.sub(" ", text)
    return LINE_COMMENT_RE.sub(" ", text)


def viewers() -> list[tuple[str, str]]:
    """(plugin, viewer path) for every plugins/*/assets/*-viewer.html, sorted."""
    found = []
    plugins_dir = os.path.join(REPO, "plugins")
    for plugin in sorted(os.listdir(plugins_dir)):
        assets = os.path.join(plugins_dir, plugin, "assets")
        if not os.path.isdir(assets):
            continue
        for name in sorted(os.listdir(assets)):
            if name.endswith("-viewer.html"):
                found.append((plugin, os.path.join(assets, name)))
    return found


def check(plugin: str, path: str) -> list[str]:
    rel = os.path.relpath(path, REPO)
    with open(path, encoding="utf-8") as fh:
        raw = fh.read()
    # Static markup only: <style> and <script> removed, then comments. R1 and R4
    # are claims about the shell a reader gets before any code runs, so anything
    # a script says about itself must not be able to satisfy them.
    markup = strip_comments(SCRIPT_RE.sub(" ", STYLE_RE.sub(" ", raw)))
    errs = []

    # S2a -- CSP. .rrt.toml calls default-src 'none' the constraint every
    # report-viewer asset needs; three viewers shipped without it.
    if "Content-Security-Policy" not in raw or "default-src 'none'" not in raw:
        errs.append(f"{rel}: S2 -- missing CSP meta with default-src 'none'")

    # S2b -- one marker spelling. Three are in use across the eight builders.
    if CANONICAL_MARKER not in raw:
        errs.append(f"{rel}: S2 -- missing canonical tokens marker {CANONICAL_MARKER}")
    for variant in VARIANT_MARKERS:
        if variant in raw:
            errs.append(f"{rel}: S2 -- non-canonical tokens marker {variant}")

    # S2c -- "<plugin> — <report noun>", lowercase plugin name.
    match = TITLE_RE.search(raw)
    if not match:
        errs.append(f"{rel}: S2 -- no <title>")
    else:
        title = match.group(1).strip()
        shape = TITLE_SHAPE.match(title)
        if not shape:
            errs.append(f"{rel}: S2 -- title {title!r} is not '<plugin> — <report noun>'")
        elif shape.group(1) != plugin:
            errs.append(f"{rel}: S2 -- title names {shape.group(1)!r}, not the plugin {plugin!r}")

    # S1 -- the header height was copy-pasted as a literal into three viewers.
    # Searched in code only: the comments explaining the fix name the old literal.
    if "61px" in strip_comments(raw):
        errs.append(f"{rel}: S1 -- hardcoded 61px header constant; use a token")

    # R1 -- the verdict, as a real element in static markup.
    if not VERDICT_RE.search(markup):
        errs.append(f"{rel}: R1 -- no static element with class=\"verdict\" stating the finding")

    # R4 -- a legend a reader gets WITHOUT interacting. A real element, because
    # confab shipped .legend CSS that nothing used and a dead renderLegend()
    # would otherwise pass. A render-time-populated legend still qualifies: its
    # CONTAINER is static markup, which is what this matches.
    if not LEGEND_RE.search(markup) and not NOTE_RE.search(markup):
        errs.append(f"{rel}: R4 -- no static legend or explanatory-note element")

    # C1/C2 -- the screenshot and its committed, cited demo data.
    shot = path[: -len(".html")] + "-screenshot.jpg"
    if not os.path.isfile(shot):
        errs.append(f"{os.path.relpath(shot, REPO)}: C1 -- screenshot missing")
    else:
        width, _ = jpeg_size(shot)
        if width != 1600:
            errs.append(f"{os.path.relpath(shot, REPO)}: C1 -- width {width}, expected 1600")

    readme = os.path.join(REPO, "plugins", plugin, "README.md")
    if os.path.isfile(readme):
        with open(readme, encoding="utf-8") as fh:
            text = fh.read()
        if "scripts/fixtures/" not in text and "scripts/testdata/" not in text:
            errs.append(f"plugins/{plugin}/README.md: C2 -- no committed demo data cited")
    else:
        errs.append(f"plugins/{plugin}/README.md: C2 -- README missing")

    return errs


def main() -> int:
    found = viewers()
    if not found:
        print("FAIL: no viewers matched plugins/*/assets/*-viewer.html", file=sys.stderr)
        return 1
    errors = []
    for plugin, path in found:
        errors.extend(check(plugin, path))
    for err in errors:
        print(f"FAIL: {err}")
    if errors:
        print(f"\n{len(errors)} violation(s) across {len(found)} viewer(s).")
        return 1
    print(f"All {len(found)} report viewer(s) conform to report-viewer-standard.md.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
