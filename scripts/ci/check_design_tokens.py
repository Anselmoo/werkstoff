#!/usr/bin/env python3
"""Check design-system surfaces for hand-rolled color/type/radius literals.

Why
---
`tools/design-tokens/tokens.css` is this repo's single source of truth for
color, and every viewer/theme surface is supposed to draw from it (via
`var(...)`) rather than re-inventing a hex literal, a raw `rgba(...)`, a
hardcoded font stack, or a bespoke corner radius. Nothing enforced that until
now -- a literal that "looks right" ships silently, drifts from the palette
the next time it changes, and nobody notices because there was never a check
to go red. This is the same shape CLAUDE.md's defect table is about: code
that looks correct and does something quietly different from what the design
system intends.

Modelled on scripts/ci/check_viewer_conformance.py (comment-stripping before
any literal search, so a comment explaining a fix is never mistaken for the
defect it fixed) and on test/plugins/lint-tag-releases.py's shrink-only
baseline (a list of known violations that may only get smaller, never grow,
never silently absorb a new one).

Rules, each counted per (path, rule):
    T-HEX         a hex colour literal (#rgb/#rgba/#rrggbb/#rrggbbaa) in a
                  VALUE position -- not a `#id` selector (recognised only in
                  actual CSS selector position: nothing between the hex and
                  the opening `{` looks like a quote, `(`, `$`, `=`, or
                  `{{`), not `href="#frag"`, not `url(#ref)`.
    T-COLOR-FN    rgb()/rgba()/hsl()/hsla()/hwb()/oklch() with a literal
                  numeric MAIN channel once every var(...) call -- nested
                  included -- is stripped out. The alpha channel is exempt
                  either syntax writes it (the tail after a top-level `/`,
                  or the 4th comma-separated argument of rgba()/hsla()), so
                  `rgba(52, 138, 217, var(--alpha))` fires (three literal
                  main channels) but `rgb(from var(--x) r g b / 0.5)` and
                  `rgba(var(--r), var(--g), var(--b), 0.5)` do not -- a
                  literal alpha alone is not a design-token concern here.
                  color-mix(...) is never matched (not one of the six
                  function names above).
    T-FONT-FAMILY font-family:/font: shorthand, or a JS `.font = "..."` /
                  `fontFamily: "..."` assignment, whose family part is a
                  literal, not var(/inherit/initial/unset/${...}. A template
                  literal whose family text is entirely `${...}` (a token
                  lookup) does not fire.
    T-RADIUS      border-radius (or border-*-radius) with a non-zero px
                  literal.

A file literally named tokens.css is exempt only when it is byte-identical to
tools/design-tokens/tokens.css (a vendored copy of the source of truth); a
hand-written or diverged tokens.css elsewhere is scanned like any other file.

Usage
-----
    python3 scripts/ci/check_design_tokens.py
    python3 scripts/ci/check_design_tokens.py --print-baseline
    python3 scripts/ci/check_design_tokens.py --base-ref origin/main
    python3 scripts/ci/check_design_tokens.py --verbose
    python3 scripts/ci/check_design_tokens.py --selftest

Exit
----
0 clean (every count matches its baseline entry exactly); 1 a count exceeds
its baseline, a baseline entry is stale (lower than the real count, or names
a file that no longer exists), or a finding has no baseline entry at all;
2 the baseline file is missing, unparseable, a scoped file could not be read,
or (with --base-ref) the ref itself does not resolve to a commit -- a failed
fetch or a typo'd ref is a hard failure, never a silent skip. A ref that
resolves but predates the baseline file's existence is a legitimate first
introduction: WARN and continue, not an error.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

SCOPE_GLOBS = (
    "docs/.vitepress/theme/**/*.css",
    "docs/.vitepress/theme/**/*.vue",
    "docs/.vitepress/theme/**/*.js",
    "docs/.vitepress/config.mjs",
    "plugins/*/assets/*-viewer.html",
    "plugins/matrize/assets/*template*.html",
)
EXCLUDED_NAME = "tokens.css"
SOURCE_TOKENS_RELPATH = Path("tools/design-tokens/tokens.css")
BASELINE_RELPATH = Path("scripts/ci/design-tokens-baseline.txt")

# --- comment stripping ------------------------------------------------------
# Same three passes as check_viewer_conformance.py's strip_comments(), and for
# the same reason: a raw substring search over a file that documents its own
# fix (a comment containing the literal it replaced) reports a violation that
# isn't there. Blanking to spaces rather than deleting keeps every remaining
# character's line number identical to the source file's, which --verbose
# depends on.
BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
HTML_COMMENT_RE = re.compile(r"<!--(?!__).*?-->", re.DOTALL)
LINE_COMMENT_RE = re.compile(r"(?<!:)//[^\n]*")


def _blank(match: re.Match[str]) -> str:
    return "".join(ch if ch == "\n" else " " for ch in match.group(0))


def strip_comments(text: str) -> str:
    """Blank CSS/JS block comments, HTML comments (not the tokens marker),
    and JS line comments (not a `scheme://` tail), preserving line numbers."""
    text = BLOCK_COMMENT_RE.sub(_blank, text)
    text = HTML_COMMENT_RE.sub(_blank, text)
    return LINE_COMMENT_RE.sub(_blank, text)


# --- T-HEX -------------------------------------------------------------------
HEX_RE = re.compile(r"#(?:[0-9A-Fa-f]{8}|[0-9A-Fa-f]{6}|[0-9A-Fa-f]{4}|[0-9A-Fa-f]{3})\b")
HREF_HEX_RE = re.compile(
    r"(?:xlink:href|href)\s*=\s*([\"'])$",
    re.IGNORECASE,
)


def _is_in_url_paren(text: str, start: int) -> bool:
    """True when `start` sits inside an unclosed `url(...)` -- `url(#grad)`
    references a local def, it is not a color value."""
    idx = text.rfind("url(", 0, start)
    if idx == -1:
        return False
    between = text[idx + 4 : start]
    return ")" not in between


def _is_href_fragment(text: str, match: re.Match[str]) -> bool:
    """True for `href="#cafe"` / `xlink:href='#cafe'` -- a fragment
    reference, not a color."""
    start, end = match.span()
    prefix = text[max(0, start - 40) : start]
    quote_match = HREF_HEX_RE.search(prefix)
    if not quote_match:
        return False
    quote = quote_match.group(1)
    return text[end : end + 1] == quote


DISQUALIFYING_BETWEEN_RE = re.compile(r"""['"`(=$]|\{\{""")


def _is_id_selector(text: str, match: re.Match[str]) -> bool:
    """True for `#bead { ... }` -- a CSS id selector, not a value. Requires
    the hex not be glued to a word/`:`/`=`/`#` before it, a `{` to open a
    rule before the next `;`/`{`/`}`/newline after it, AND the text between
    the hex and that `{` to hold nothing but selector syntax: a lone `{`
    reached only by crossing a quote, `(`, `$`, `=`, or `{{` first is a JS
    arrow-function body, a template placeholder, or an object/attribute
    literal -- not a CSS rule opening -- so the hex is a real value there,
    not an id selector (e.g. `sel.attr('fill', '#ab6dc6').on('click', (e, d)
    => { ... })`, `style="color: #ff0000">${esc(n.name)}`, `fill="#ee1122"
    r="${r}"`, Vue's `style="color: #ff0000">{{ label }}`)."""
    start, end = match.span()
    prev = text[start - 1] if start > 0 else ""
    if prev and (prev.isalnum() or prev in "#:=_-"):
        return False
    tail = text[end:]
    boundary = re.match(r"[^;{}\n]*", tail)
    stop = boundary.end() if boundary else 0
    if tail[stop : stop + 1] != "{":
        return False
    return not DISQUALIFYING_BETWEEN_RE.search(tail[:stop])


def scan_hex(text: str) -> list[re.Match[str]]:
    findings = []
    for match in HEX_RE.finditer(text):
        if _is_in_url_paren(text, match.start()):
            continue
        if _is_href_fragment(text, match):
            continue
        if _is_id_selector(text, match):
            continue
        findings.append(match)
    return findings


# --- T-COLOR-FN ---------------------------------------------------------------
# Only the call's NAME and opening paren; its arguments are read by _call_args(), which
# balances parentheses to any depth. A regex for the arguments cannot: the previous one
# handled one level of nesting, so rgba(var(--r, var(--f)), 2, 3, 0.5) never matched and its
# literal main channels passed.
COLOR_FN_RE = re.compile(r"\b(?:rgb|rgba|hsl|hsla|hwb|oklch)\(", re.IGNORECASE)
DIGIT_RE = re.compile(r"\d")


def _strip_var_calls(value: str) -> str:
    """Remove every var(...) call, nested parens included -- e.g.
    var(--x, var(--y, 3)) disappears whole, not just its outer wrapper."""
    out = []
    i, n = 0, len(value)
    lower = value.lower()
    while i < n:
        if lower.startswith("var(", i):
            depth = 1
            j = i + 4
            while j < n and depth:
                if value[j] == "(":
                    depth += 1
                elif value[j] == ")":
                    depth -= 1
                j += 1
            i = j
        else:
            out.append(value[i])
            i += 1
    return "".join(out)


def _split_top_level(value: str) -> list[str]:
    """Split on commas that are not inside parens -- so a var(--x, 3) inside
    one argument does not get mistaken for an argument separator."""
    parts: list[str] = []
    current: list[str] = []
    depth = 0
    for ch in value:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append("".join(current))
            current = []
        else:
            current.append(ch)
    parts.append("".join(current))
    return parts


def _has_literal_main_channel(args: str) -> bool:
    """True when a MAIN colour channel -- not the alpha channel -- is a
    literal number once every var(...) call is stripped out. The alpha
    channel is exempt under either syntax the arguments use: the tail after
    a top-level `/` (`rgb(from var(--x) r g b / 0.5)`), or the fourth
    comma-separated argument of rgba()/hsla() (`rgba(52, 138, 217, 0.5)`'s
    trailing 0.5). A literal alpha alone never trips this rule; a literal
    main channel always does."""
    if "/" in args:
        main = args.rsplit("/", 1)[0]
    else:
        parts = _split_top_level(args)
        main = ",".join(parts[:3]) if len(parts) == 4 else args
    return bool(DIGIT_RE.search(_strip_var_calls(main)))


class CallMatch:
    """The part of re.Match that scan_file() and the selftest read: where the call starts,
    and its full argument text."""

    def __init__(self, start: int, args: str) -> None:
        self._start = start
        self._args = args

    def start(self) -> int:
        return self._start

    def group(self, index: int = 0) -> str:
        return self._args


def _call_args(text: str, open_paren: int) -> str:
    """The argument text of the call whose `(` sits at `open_paren`, nested calls included.
    An unclosed call is read to the end of its line rather than skipped: malformed CSS is no
    reason to stop checking it."""
    depth = 0
    for i in range(open_paren, len(text)):
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                return text[open_paren + 1 : i]
    end = text.find("\n", open_paren)
    return text[open_paren + 1 : end if end != -1 else len(text)]


def scan_color_fn(text: str) -> list[CallMatch]:
    hits = []
    for match in COLOR_FN_RE.finditer(text):
        args = _call_args(text, match.end() - 1)
        if _has_literal_main_channel(args):
            hits.append(CallMatch(match.start(), args))
    return hits


# --- T-FONT-FAMILY -------------------------------------------------------------
# Where a CSS declaration ends: its `;`, the `}` closing its block (CSS lets the last
# declaration omit the `;`, so requiring one let `font-family: Arial}` through), or the `"`
# closing an inline style attribute.
DECL_END = r'(?=;|\}|"\s*(?:/?>|[\w:-]+\s*=))'
FONT_PROP_RE = re.compile(r"\bfont(?:-family)?\s*:\s*([^;}]+?)" + DECL_END, re.IGNORECASE)
# JS font assignments: `ctx.font = '12px Arial'` (canvas) and
# `fontFamily: '...'` / `el.style.fontFamily = '...'` (DOM/React/Vue). Only
# an assignment or object-property colon counts -- not a bare mention of the
# word `font` in prose or a variable name.
JS_FONT_ASSIGN_RE = re.compile(
    r"(?:\.font\s*=\s*|\bfontFamily\s*[:=]\s*)"
    r"(`(?:[^`\\]|\\.)*`|'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\")"
)
VAR_CALL_RE = re.compile(r"var\([^)]*\)", re.IGNORECASE)
JS_INTERP_RE = re.compile(r"\$\{[^}]*\}")
FONT_TOKEN_SPLIT_RE = re.compile(r"[\s,/]+")
FONT_KEYWORDS = {
    "inherit", "initial", "unset", "revert", "revert-layer",
    "normal", "italic", "oblique", "small-caps",
    "bold", "bolder", "lighter",
    "caption", "icon", "menu", "message-box", "small-caption", "status-bar",
}
SIZE_TOKEN_RE = re.compile(
    r"^\d+(?:\.\d+)?(?:px|em|rem|%|pt|ex|ch|vw|vh)?$", re.IGNORECASE
)


def _literal_family_present(value: str) -> bool:
    """True when `value` (a font/font-family declaration's RHS, or a JS
    font-assignment's string contents) names a literal family -- something
    left over once every var(...) call, every `${...}` template
    substitution, bare size/line-height number, and shorthand keyword (bold,
    inherit, ...) is accounted for. A template literal whose family text is
    entirely `${...}` (a token lookup, e.g. `` `${tokenFontFamily}` ``)
    leaves nothing behind and does not fire."""
    without_vars = VAR_CALL_RE.sub("", value)
    without_interp = JS_INTERP_RE.sub("", without_vars)
    tokens = [t for t in FONT_TOKEN_SPLIT_RE.split(without_interp) if t]
    for token in tokens:
        if token.lower() in FONT_KEYWORDS:
            continue
        if SIZE_TOKEN_RE.match(token):
            continue
        return True
    return False


def scan_font_family(text: str) -> list[re.Match[str]]:
    css_hits = [m for m in FONT_PROP_RE.finditer(text) if _literal_family_present(m.group(1))]
    js_hits = [m for m in JS_FONT_ASSIGN_RE.finditer(text) if _literal_family_present(m.group(1)[1:-1])]
    return css_hits + js_hits


# --- T-RADIUS ------------------------------------------------------------------
RADIUS_PROP_RE = re.compile(
    r"\bborder(?:-(?:top|bottom)-(?:left|right))?-radius\s*:\s*([^;}]+?)" + DECL_END, re.IGNORECASE
)
PX_TOKEN_RE = re.compile(r"(-?\d*\.?\d+)px", re.IGNORECASE)


def scan_radius(text: str) -> list[re.Match[str]]:
    findings = []
    for match in RADIUS_PROP_RE.finditer(text):
        for px_match in PX_TOKEN_RE.finditer(match.group(1)):
            if float(px_match.group(1)) != 0:
                findings.append(match)
                break
    return findings


RULE_SCANNERS = (
    ("T-HEX", scan_hex),
    ("T-COLOR-FN", scan_color_fn),
    ("T-FONT-FAMILY", scan_font_family),
    ("T-RADIUS", scan_radius),
)


class ScanError(Exception):
    """A structural problem (unreadable file, unparseable baseline) that
    must fail the run loudly rather than report an empty pass."""


# --- discovery -----------------------------------------------------------------
def _is_source_tokens_copy(root: Path, path: Path) -> bool:
    """True only when `path` is named tokens.css AND is byte-identical to
    tools/design-tokens/tokens.css -- a legitimate vendored copy of the
    source of truth. A file that merely happens to be called tokens.css but
    has diverged (hand-written, stale, or otherwise different content) is
    not exempt and gets scanned like any other file; nor is it exempt when
    the source itself is missing or unreadable."""
    if path.name != EXCLUDED_NAME:
        return False
    source = root / SOURCE_TOKENS_RELPATH
    try:
        if not source.is_file():
            return False
        return path.read_bytes() == source.read_bytes()
    except OSError:
        return False


def _glob_regex(pattern: str) -> re.Pattern[str]:
    """A SCOPE_GLOBS pattern as a regex over a posix path relative to the repo root:
    `**/` spans zero or more directories, `*` and `?` stay within one."""
    out = []
    i = 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out.append("(?:[^/]+/)*")
            i += 3
        elif pattern[i] == "*":
            out.append("[^/]*")
            i += 1
        elif pattern[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    return re.compile("".join(out) + r"\Z")


SCOPE_REGEXES = tuple(_glob_regex(pattern) for pattern in SCOPE_GLOBS)
# Every SCOPE_GLOBS pattern lives under one of these; nothing else is walked.
SCOPE_TOPS = ("docs/.vitepress", "plugins")
# Directories no scope pattern can reach, skipped for speed: dependencies, VCS data, and the
# docs site's build output and cache.
PRUNED = {"node_modules", ".git"}
PRUNED_UNDER_VITEPRESS = {"dist", "cache"}


def _walk_files(root: Path, top: str) -> list[str]:
    """Every file under `root/top`, as a posix path relative to `root`.

    os.walk() with an onerror that raises, NOT Path.glob(): glob() swallows a PermissionError
    and returns no matches for a directory it cannot read, which would turn an unreadable
    viewer directory into a clean, incomplete audit. Here it fails the run instead."""
    base = root / top
    if not base.is_dir():
        return []

    def fail(exc: OSError) -> None:
        raise ScanError(f"cannot traverse {exc.filename}: {exc}") from exc

    rels = []
    for dirpath, dirnames, filenames in os.walk(base, onerror=fail):
        here = Path(dirpath)
        prune = PRUNED | (PRUNED_UNDER_VITEPRESS if here == root / "docs/.vitepress" else set())
        dirnames[:] = [d for d in dirnames if d not in prune]
        rels.extend((here / name).relative_to(root).as_posix() for name in filenames)
    return rels


def discovered_files(root: Path) -> list[Path]:
    """Every file the scope globs name, minus a tokens.css that is a byte-identical copy of the
    source of truth. Raises ScanError when a directory in scope cannot be read."""
    found: set[Path] = set()
    for top in SCOPE_TOPS:
        for rel in _walk_files(root, top):
            if any(rx.match(rel) for rx in SCOPE_REGEXES):
                found.add(root / rel)
    return sorted(p for p in found if not _is_source_tokens_copy(root, p))


# --- scanning --------------------------------------------------------------
def _line_no(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def _excerpt(text: str, pos: int) -> str:
    start = text.rfind("\n", 0, pos) + 1
    end = text.find("\n", pos)
    if end == -1:
        end = len(text)
    return text[start:end].strip()


def scan_file(path: Path) -> dict[str, list[tuple[int, str]]]:
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise ScanError(f"cannot read {path}: {exc}") from exc
    text = strip_comments(raw)
    results: dict[str, list[tuple[int, str]]] = {}
    for rule, scanner in RULE_SCANNERS:
        matches = scanner(text)
        if matches:
            results[rule] = [(_line_no(text, m.start()), _excerpt(text, m.start())) for m in matches]
    return results


def scan_repo(
    root: Path, files: list[Path]
) -> tuple[dict[tuple[str, str], int], list[tuple[str, int, str, str]]]:
    current: dict[tuple[str, str], int] = {}
    findings: list[tuple[str, int, str, str]] = []
    for path in files:
        rel = path.relative_to(root).as_posix()
        for rule, entries in scan_file(path).items():
            current[(rel, rule)] = len(entries)
            for line, excerpt in entries:
                findings.append((rel, line, rule, excerpt))
    return current, findings


# --- baseline ----------------------------------------------------------------
def parse_baseline(text: str) -> dict[tuple[str, str], int]:
    result: dict[tuple[str, str], int] = {}
    for lineno, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) != 3:
            raise ScanError(f"baseline line {lineno} is not 'path<TAB>rule<TAB>count': {line!r}")
        path, rule, count_text = parts
        try:
            count = int(count_text)
        except ValueError as exc:
            raise ScanError(f"baseline line {lineno}: non-integer count {count_text!r}") from exc
        result[(path, rule)] = count
    return result


def format_baseline(current: dict[tuple[str, str], int]) -> str:
    lines = [
        "# Design-token hygiene baseline. Shrink-only -- see scripts/ci/check_design_tokens.py.",
        "# Regenerate with: python3 scripts/ci/check_design_tokens.py --print-baseline",
    ]
    for path, rule in sorted(current):
        lines.append(f"{path}\t{rule}\t{current[(path, rule)]}")
    return "\n".join(lines) + "\n"


def compare(
    current: dict[tuple[str, str], int], baseline: dict[tuple[str, str], int], root: Path
) -> list[str]:
    """Every baseline rule from CLAUDE.md's HARD RULES section, applied:
    above baseline fails naming both counts; below baseline (including a
    finding that vanished entirely) is reported stale so the list can only
    shrink; a finding with no baseline entry at all fails; a baseline entry
    for a file that no longer exists fails as stale."""
    failures = []
    for path, rule in sorted(set(current) | set(baseline)):
        key = (path, rule)
        cur = current.get(key, 0)
        base = baseline.get(key)
        if key in baseline and not (root / path).is_file():
            failures.append(f"STALE: {path}\t{rule}: baseline names a file that no longer exists")
            continue
        if base is None:
            failures.append(f"NEW: {path}\t{rule}: {cur} finding(s) with no baseline entry")
            continue
        if cur > base:
            failures.append(f"FAIL: {path}\t{rule}: {cur} finding(s) exceeds baseline {base}")
        elif cur < base:
            failures.append(
                f"STALE: {path}\t{rule}: baseline says {base}, only {cur} found -- lower the baseline to {cur}"
            )
    return failures


class BaseRefError(Exception):
    """The base ref itself does not resolve to a commit -- a failed
    `git fetch`, a typo'd ref, or git being unavailable at all. Distinct
    from a ref that resolves fine but simply predates the baseline file's
    existence (a legitimate first introduction, handled as WARN+continue in
    read_git_baseline rather than raised here)."""


def _ref_exists(root: Path, ref: str) -> bool:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--verify", f"{ref}^{{commit}}"],
            cwd=root,
            capture_output=True,
            text=True,
        )
    except OSError:
        return False
    return result.returncode == 0


def read_git_baseline(root: Path, ref: str) -> dict[tuple[str, str], int] | None:
    """Raises BaseRefError when `ref` does not resolve to a commit at all
    (unresolvable -- caller must fail hard, not silently skip the
    grew-baseline guard). Returns None, after printing a WARN, only for the
    legitimate case where `ref` resolves but the baseline file did not exist
    there yet (first introduction) or is unparseable."""
    if not _ref_exists(root, ref):
        raise BaseRefError(f"base ref does not resolve to a commit: {ref!r}")
    try:
        result = subprocess.run(
            ["git", "show", f"{ref}:{BASELINE_RELPATH.as_posix()}"],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        print(
            f"WARN: baseline file absent at {ref} (treated as first introduction): {exc}",
            file=sys.stderr,
        )
        return None
    try:
        return parse_baseline(result.stdout)
    except ScanError as exc:
        print(f"WARN: baseline at {ref} is unparseable: {exc}", file=sys.stderr)
        return None


#: Files renamed in flight, mapping CURRENT path -> the path it had at the base
#: ref. A rename makes a baseline key look new to compare_against_ref, which
#: cannot otherwise tell it from an added one -- the same collision ruff.toml's
#: shrink-only baseline has, except that this check also compares against git.
#:
#: This lives here rather than in the baseline file because --print-baseline
#: regenerates that file from scratch and would silently drop it.
#:
#: SHRINK-ONLY STILL HOLDS: a renamed key's count may not exceed the count its
#: old path carried at the base ref. An entry is STALE once the base ref carries
#: the new path -- compare_against_ref reports that, and the line must be deleted.
BASELINE_RENAMES: dict[str, str] = {
    "plugins/befund/assets/stage-map-viewer.html": "plugins/self-assess/assets/stage-map-viewer.html",
    "plugins/passung/assets/matrix-viewer.html": "plugins/codebase-consistency/assets/matrix-viewer.html",
    "plugins/zeugnis/assets/burndown-viewer.html": "plugins/confab/assets/burndown-viewer.html",
    "plugins/zirkel/assets/branch-comparison-viewer.html": "plugins/compass/assets/branch-comparison-viewer.html",
}


def compare_against_ref(
    working: dict[tuple[str, str], int],
    ref_baseline: dict[tuple[str, str], int],
    renames: dict[str, str] | None = None,
) -> list[str]:
    """Shrink-only across history too: the working baseline may never carry
    a higher count, or a new (path, rule), than the ref it is compared to.

    `renames` maps a current path to its pre-rename path, so a moved file is
    compared against its own old entry instead of read as a new one."""
    renames = BASELINE_RENAMES if renames is None else renames
    failures = []
    for old_path, new_path in sorted(renames.items()):
        if any(k[0] == old_path for k in ref_baseline):
            failures.append(
                f"FAIL: {old_path}\tBASELINE_RENAMES maps it to {new_path!r}, but the base "
                f"ref already carries the current path -- the entry is stale, delete it"
            )
    for path, rule in sorted(working):
        key = (path, rule)
        count = working[key]
        if key in ref_baseline:
            if count > ref_baseline[key]:
                failures.append(
                    f"FAIL: {path}\t{rule}: baseline count {count} exceeds {ref_baseline[key]} at the base ref"
                )
            continue
        pre_rename = (renames.get(path), rule)
        if pre_rename[0] is not None and pre_rename in ref_baseline:
            if count > ref_baseline[pre_rename]:
                failures.append(
                    f"FAIL: {path}\t{rule}: baseline count {count} exceeds "
                    f"{ref_baseline[pre_rename]} carried at the base ref by its pre-rename "
                    f"path {pre_rename[0]}"
                )
            continue
        failures.append(
            f"FAIL: {path}\t{rule}: new baseline entry absent from the base ref (baseline may only shrink)"
        )
    return failures


# --- selftest ------------------------------------------------------------------
def _write_fixture_tree(root: Path) -> None:
    (root / "docs/.vitepress/theme/components").mkdir(parents=True)
    (root / "docs/.vitepress/theme/overrides").mkdir(parents=True)
    (root / "plugins/demo/assets").mkdir(parents=True)
    (root / "plugins/matrize/assets").mkdir(parents=True)
    (root / "tools/design-tokens").mkdir(parents=True)

    (root / "docs/.vitepress/theme/sample.css").write_text(
        "/* comment: #ff00ff must not fire */\n"
        ".value {\n"
        "  color: #ff0000;\n"
        "  background: rgba(1, 2, 3, 0.5);\n"
        "  outline-color: hsl(200, 50%, 50%);\n"
        "  border: 1px solid var(--x);\n"
        "  mask: url(#cafe);\n"
        "  font-family: Arial, sans-serif;\n"
        "  font: var(--wk-font-size)/var(--wk-line-height) var(--wk-font-sans);\n"
        "}\n"
        ".radius {\n"
        "  border-radius: 10px;\n"
        "}\n"
        ".radius-zero {\n"
        "  border-radius: 0;\n"
        "}\n"
        "#bead {\n"
        "  color: blue;\n"
        "}\n"
        ".mix {\n"
        "  background: color-mix(in srgb, var(--x) 20%, transparent);\n"
        "}\n"
        ".alpha-main {\n"
        "  background: rgba(52, 138, 217, var(--alpha));\n"
        "}\n"
        ".alpha-only {\n"
        "  background: rgb(from var(--x) r g b / 0.5);\n"
        "  border-color: rgba(var(--r), var(--g), var(--b), 0.5);\n"
        "}\n",
        encoding="utf-8",
    )
    # The source of truth. Never itself in SCOPE_GLOBS, but its presence and
    # content are what makes the vendored copy below exempt.
    (root / "tools/design-tokens/tokens.css").write_text(
        ":root {\n  --wk-color: #112233;\n}\n", encoding="utf-8"
    )
    (root / "docs/.vitepress/theme/tokens.css").write_text(
        (root / "tools/design-tokens/tokens.css").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    # A file also named tokens.css, but hand-written and diverged from the
    # source -- must be scanned like any other file, not exempted by name.
    (root / "docs/.vitepress/theme/overrides/tokens.css").write_text(
        ".hand-written {\n  color: #ff0000;\n}\n", encoding="utf-8"
    )
    (root / "docs/.vitepress/config.mjs").write_text(
        "export default { base: '/x/' }\n", encoding="utf-8"
    )
    (root / "docs/.vitepress/theme/components/Sample.vue").write_text(
        "<template><div class=\"x\"></div></template>\n"
        "<script>\nexport default { name: 'Sample' }\n</script>\n"
        "<style>\n.bar { color: #123456; }\n</style>\n",
        encoding="utf-8",
    )
    (root / "plugins/demo/assets/demo-viewer.html").write_text(
        "<!--__DESIGN_TOKENS__-->\n"
        "<html><body>\n"
        '<svg><a href="#cafe">ref</a></svg>\n'
        "<script>\n"
        "const c = '#5b7fa6';\n"
        "</script>\n"
        "</body></html>\n",
        encoding="utf-8",
    )
    (root / "plugins/matrize/assets/foo-template.html").write_text(
        '<div style="color:#abcdef"></div>\n', encoding="utf-8"
    )


def selftest() -> bool:
    print("check_design_tokens --selftest")
    passed = 0
    failed = 0

    def check(name: str, ok: bool, detail: str = "") -> None:
        nonlocal passed, failed
        if ok:
            print(f"  ok   {name}")
            passed += 1
        else:
            print(f"  FAIL {name}{': ' + detail if detail else ''}")
            failed += 1

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_fixture_tree(root)
        files = discovered_files(root)
        disc = {p.relative_to(root).as_posix() for p in files}

        check(
            "discovery includes docs/.vitepress/config.mjs",
            "docs/.vitepress/config.mjs" in disc,
        )
        check(
            "discovery excludes a tokens.css byte-identical to the source of truth",
            "docs/.vitepress/theme/tokens.css" not in disc,
        )
        override = "docs/.vitepress/theme/overrides/tokens.css"
        check(
            "discovery still scans a tokens.css that diverged from the source of truth",
            override in disc,
        )

        current, findings = scan_repo(root, files)

        check(
            "a diverged tokens.css fires on its own hex literal (T-HEX)",
            current.get((override, "T-HEX")) == 1,
        )

        css = "docs/.vitepress/theme/sample.css"
        check("fires on hex in a CSS value (T-HEX)", current.get((css, "T-HEX")) == 1)
        check(
            "fires on rgba(...)/hsl(...) literals and a literal main channel "
            "beside a var() alpha, silent on an alpha-only literal (T-COLOR-FN)",
            current.get((css, "T-COLOR-FN")) == 3,
        )
        check("fires on a literal font-family (T-FONT-FAMILY)", current.get((css, "T-FONT-FAMILY")) == 1)
        check("fires on border-radius: 10px (T-RADIUS)", current.get((css, "T-RADIUS")) == 1)
        check(
            "silent on hex in a CSS comment, var(--x), color-mix(...), "
            "#bead id selector, url(#cafe), border-radius: 0",
            current.get((css, "T-HEX")) == 1 and current.get((css, "T-RADIUS")) == 1,
        )

        vue_path = "docs/.vitepress/theme/components/Sample.vue"
        check("fires on hex inside a .vue <style>", current.get((vue_path, "T-HEX")) == 1)

        viewer = "plugins/demo/assets/demo-viewer.html"
        check("fires on hex in a viewer JS string", current.get((viewer, "T-HEX")) == 1)
        viewer_finding_lines = [line for path, line, rule, _ in findings if path == viewer and rule == "T-HEX"]
        check("silent on href=\"#cafe\" and the tokens marker line", viewer_finding_lines == [5])

        template = "plugins/matrize/assets/foo-template.html"
        check("fires on hex in an inline style attribute", current.get((template, "T-HEX")) == 1)

        # --- T-HEX: id-selector heuristic must not swallow a real value just
        # because SOME later character on the line is a `{` (finding 2) ---
        check(
            "T-HEX fires through a trailing arrow-function `{` (d3-style .attr().on())",
            len(scan_hex("sel.attr('fill', '#ab6dc6').on('click', (e, d) => { select(d); });")) == 1,
        )
        check(
            "T-HEX fires before a template literal's ${...} interpolation",
            len(scan_hex('const t = `<span style="color: #ff0000">${esc(n.name)}</span>`;')) == 1,
        )
        check(
            "T-HEX fires in a self-closing tag whose attribute is ${...}",
            len(scan_hex('const t = `<rect fill="#ee1122" r="${r}"/>`;')) == 1,
        )
        check(
            "T-HEX fires before a Vue {{ mustache }}",
            len(scan_hex('const t = `<span style="color: #ff0000">{{ label }}</span>`;')) == 1,
        )
        check(
            "T-HEX still stays silent on a real id selector",
            len(scan_hex("body { margin: 0; }\n#bead {\n  color: blue;\n}\n")) == 0,
        )

        # --- T-FONT-FAMILY: JS assignments, not just CSS properties (finding 1) ---
        check(
            "T-FONT-FAMILY fires on a canvas ctx.font assignment",
            len(scan_font_family("ctx.font = '12px Arial';")) == 1,
        )
        check(
            "T-FONT-FAMILY fires on a fontFamily: '...' object property",
            len(scan_font_family("const s = { fontFamily: 'Helvetica, sans-serif' };")) == 1,
        )
        check(
            "T-FONT-FAMILY silent when a template literal's family part is entirely "
            "a ${...} token lookup",
            len(scan_font_family("const s = { fontFamily: `${tokenFontFamily}` };")) == 0,
        )

        # --- T-COLOR-FN: alpha channel is exempt, main channels are not (finding 4) ---
        check(
            "T-COLOR-FN fires when main channels are literal even though alpha is var()",
            len(scan_color_fn("rgba(52, 138, 217, var(--alpha))")) == 1,
        )
        check(
            "T-COLOR-FN silent when only the alpha channel is literal (slash syntax)",
            len(scan_color_fn("rgb(from var(--x) r g b / 0.5)")) == 0,
        )
        check(
            "T-COLOR-FN silent when only the alpha channel is literal (comma syntax)",
            len(scan_color_fn("rgba(var(--r), var(--g), var(--b), 0.5)")) == 0,
        )
        check(
            "T-COLOR-FN never matches color-mix(...) -- not one of the six named functions",
            len(scan_color_fn("color-mix(in srgb, var(--x) 20%, transparent)")) == 0,
        )

        # --- review findings: nesting, declaration boundaries, traversal ---
        check(
            "T-COLOR-FN fires on literal main channels beside a NESTED var() fallback",
            len(scan_color_fn("rgba(var(--r, var(--fallback)), 2, 3, 0.5)")) == 1,
        )
        check(
            "T-COLOR-FN stays silent when every main channel is a nested var()",
            len(scan_color_fn("rgba(var(--r, var(--f)), var(--g), var(--b), 0.5)")) == 0,
        )
        check(
            "T-FONT-FAMILY fires on a last declaration with no `;` before `}`",
            len(scan_font_family(".a { color: red; font-family: Arial }")) == 1
            and len(scan_font_family(".a { font: 12px Arial}")) == 1,
        )
        check(
            "T-FONT-FAMILY fires inside an inline style attribute with no `;`",
            len(scan_font_family('<div style="font-family: Arial">x</div>')) == 1,
        )
        check(
            "T-FONT-FAMILY still silent on a semicolonless var() declaration",
            len(scan_font_family(".a { font-family: var(--font-mono) }")) == 0,
        )
        check(
            "T-RADIUS fires on a last declaration with no `;` before `}`",
            len(scan_radius(".a { border-radius: 4px }")) == 1,
        )
        locked = root / "plugins/locked"
        (locked / "assets").mkdir(parents=True)
        locked.chmod(0)
        try:
            if os.access(locked, os.R_OK):
                print("  skip unreadable-directory case: permissions are not enforced for this user")
            else:
                try:
                    discovered_files(root)
                    raised = False
                except ScanError:
                    raised = True
                check("discovery RAISES on an unreadable directory instead of skipping it", raised)
        finally:
            locked.chmod(0o755)

        # --- baseline behaviour ---
        existing = css
        missing = "docs/.vitepress/theme/does-not-exist.css"
        inc = compare({(existing, "T-HEX"): 5}, {(existing, "T-HEX"): 2}, root)
        check("baseline: an increase fails", any(f.startswith("FAIL:") and existing in f for f in inc))

        dec = compare({(existing, "T-HEX"): 1}, {(existing, "T-HEX"): 5}, root)
        check("baseline: a decrease is reported stale", any(f.startswith("STALE:") and existing in f for f in dec))

        new = compare({(existing, "T-HEX"): 1}, {}, root)
        check("baseline: an unlisted finding fails", any(existing in f for f in new))

        gone = compare({}, {(missing, "T-HEX"): 3}, root)
        check(
            "baseline: an entry for a missing file is stale",
            any(f.startswith("STALE:") and missing in f for f in gone),
        )

        # --- compare_against_ref: shrink-only across history too (finding 3) ---
        ref_inc = compare_against_ref({(existing, "T-HEX"): 3}, {(existing, "T-HEX"): 2})
        check(
            "compare_against_ref: a working count above the ref's fails",
            any(f.startswith("FAIL:") and existing in f for f in ref_inc),
        )

        ref_missing_key = compare_against_ref({(existing, "T-HEX"): 1}, {})
        check(
            "compare_against_ref: a key absent from the ref baseline fails",
            any(f.startswith("FAIL:") and existing in f for f in ref_missing_key),
        )

        ref_equal = compare_against_ref({(existing, "T-HEX"): 2}, {(existing, "T-HEX"): 2})
        check("compare_against_ref: an equal count yields nothing", ref_equal == [])

        ref_lower = compare_against_ref({(existing, "T-HEX"): 1}, {(existing, "T-HEX"): 2})
        check("compare_against_ref: a lower count yields nothing", ref_lower == [])

        # --- BASELINE_RENAMES: a moved file is not a new one, and the exemption
        # must stay narrow enough that it cannot launder a real increase.
        _ren = {"new/v.html": "old/v.html"}
        ren_ok = compare_against_ref(
            {("new/v.html", "T-HEX"): 2}, {("old/v.html", "T-HEX"): 2}, _ren
        )
        check("renames: a moved key matches its pre-rename entry", ren_ok == [])

        ren_lower = compare_against_ref(
            {("new/v.html", "T-HEX"): 1}, {("old/v.html", "T-HEX"): 2}, _ren
        )
        check("renames: a moved key that shrank yields nothing", ren_lower == [])

        ren_grew = compare_against_ref(
            {("new/v.html", "T-HEX"): 3}, {("old/v.html", "T-HEX"): 2}, _ren
        )
        check(
            "renames: a moved key whose count GREW still fails",
            any("pre-rename" in f and f.startswith("FAIL:") for f in ren_grew),
        )

        ren_other = compare_against_ref(
            {("unrelated/v.html", "T-HEX"): 1}, {("old/v.html", "T-HEX"): 2}, _ren
        )
        check(
            "renames: an unrelated new key still fails (exemption stays narrow)",
            any("unrelated/v.html" in f and f.startswith("FAIL:") for f in ren_other),
        )

        ren_stale = compare_against_ref(
            {("new/v.html", "T-HEX"): 1},
            {("old/v.html", "T-HEX"): 1, ("new/v.html", "T-HEX"): 1},
            _ren,
        )
        check(
            "renames: an entry whose old path is still in the ref is reported stale",
            any("stale" in f for f in ren_stale),
        )

        ren_wrong_rule = compare_against_ref(
            {("new/v.html", "T-RADIUS"): 1}, {("old/v.html", "T-HEX"): 1}, _ren
        )
        check(
            "renames: the rule must match too, not just the path",
            any("T-RADIUS" in f and "new baseline entry" in f for f in ren_wrong_rule),
        )

        original_compare_against_ref = globals()["compare_against_ref"]
        globals()["compare_against_ref"] = lambda working, ref: []
        try:
            sab_ref_inc = compare_against_ref({(existing, "T-HEX"): 3}, {(existing, "T-HEX"): 2})
        finally:
            globals()["compare_against_ref"] = original_compare_against_ref
        check(
            "sabotage: a blanked compare_against_ref stops flagging a real "
            "grew-baseline increase (proves the checks above are load-bearing)",
            sab_ref_inc == [],
        )

        no_baseline_rc = main(["--root", str(root), "--baseline", str(root / "nope.txt")])
        check("missing baseline file exits 2", no_baseline_rc == 2)

        # --- sabotage: each rule's finding must depend on its own pattern ---
        never = re.compile(r"(?!)")

        def sabotage(global_name: str, path: str, rule: str, case_name: str) -> None:
            original = globals()[global_name]
            globals()[global_name] = never
            try:
                sab_current, _ = scan_repo(root, files)
                gone_finding = sab_current.get((path, rule), 0) == 0
            finally:
                globals()[global_name] = original
            check(f"sabotage: {case_name} depends on its own pattern", gone_finding)

        sabotage("HEX_RE", css, "T-HEX", "T-HEX")
        sabotage("COLOR_FN_RE", css, "T-COLOR-FN", "T-COLOR-FN")
        sabotage("FONT_PROP_RE", css, "T-FONT-FAMILY", "T-FONT-FAMILY")
        sabotage("RADIUS_PROP_RE", css, "T-RADIUS", "T-RADIUS")

    # --- read_git_baseline / BaseRefError: an unresolvable ref must be
    # distinguished from one that simply predates the baseline file
    # (finding 6). Uses a real temp git repo, not a mock. ---
    with tempfile.TemporaryDirectory() as git_tmp:
        git_root = Path(git_tmp)

        def _git(args: list[str]) -> None:
            subprocess.run(["git", *args], cwd=git_root, check=True, capture_output=True, text=True)

        def _head_sha() -> str:
            return subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=git_root, capture_output=True, text=True, check=True
            ).stdout.strip()

        _git(["init", "-q"])
        _git(["config", "user.email", "test@example.com"])
        _git(["config", "user.name", "Test"])
        (git_root / "README.md").write_text("x\n", encoding="utf-8")
        _git(["add", "README.md"])
        _git(["commit", "-q", "-m", "no baseline file yet"])
        no_baseline_sha = _head_sha()

        check(
            "read_git_baseline: a resolvable ref without the baseline file WARNs and returns None",
            read_git_baseline(git_root, no_baseline_sha) is None,
        )

        raised = False
        try:
            read_git_baseline(git_root, "refs/heads/definitely-not-a-branch")
        except BaseRefError:
            raised = True
        check(
            "read_git_baseline: an unresolvable ref raises BaseRefError instead of WARNing",
            raised,
        )

        (git_root / BASELINE_RELPATH.parent).mkdir(parents=True, exist_ok=True)
        (git_root / BASELINE_RELPATH).write_text("a/b.css\tT-HEX\t1\n", encoding="utf-8")
        _git(["add", str(BASELINE_RELPATH)])
        _git(["commit", "-q", "-m", "add baseline"])
        check(
            "read_git_baseline: a resolvable ref with the baseline file parses it",
            read_git_baseline(git_root, _head_sha()) == {("a/b.css", "T-HEX"): 1},
        )

        # main(): an unresolvable --base-ref is ERROR + exit 2, never a silent skip.
        (git_root / "plugins/demo/assets").mkdir(parents=True, exist_ok=True)
        (git_root / "plugins/demo/assets/demo-viewer.html").write_text("<html></html>\n", encoding="utf-8")
        main_bad_ref_rc = main(
            [
                "--root", str(git_root),
                "--baseline", str(git_root / BASELINE_RELPATH),
                "--base-ref", "refs/heads/definitely-not-a-branch",
            ]
        )
        check("main(): an unresolvable --base-ref exits 2", main_bad_ref_rc == 2)

    print(f"selftest: {passed} passed, {failed} failed")
    return failed == 0


# --- main ------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", default=None, help="repo root (default: this script's repo)")
    parser.add_argument(
        "--baseline",
        default=None,
        help=f"baseline file (default: <root>/{BASELINE_RELPATH.as_posix()})",
    )
    parser.add_argument(
        "--print-baseline",
        action="store_true",
        help="print current counts in baseline format to stdout and exit 0 (never writes a file)",
    )
    parser.add_argument(
        "--base-ref",
        default=None,
        help="git ref whose baseline the working baseline must not exceed (shrink-only across history)",
    )
    parser.add_argument("--verbose", action="store_true", help="list each finding as path:line: rule: excerpt")
    parser.add_argument("--selftest", action="store_true", help="run the planted-defect self-test and exit")
    args = parser.parse_args(argv)

    if args.selftest:
        return 0 if selftest() else 1

    root = Path(args.root).resolve() if args.root else REPO
    files = discovered_files(root)
    if not files:
        print(
            "check_design_tokens: no files matched the scope globs -- refusing to report "
            "success on an empty set",
            file=sys.stderr,
        )
        return 2

    try:
        current, findings = scan_repo(root, files)
    except ScanError as exc:
        print(f"check_design_tokens: {exc}", file=sys.stderr)
        return 2

    if args.verbose:
        for path, line, rule, excerpt in sorted(findings):
            print(f"{path}:{line}: {rule}: {excerpt}")

    if args.print_baseline:
        sys.stdout.write(format_baseline(current))
        return 0

    baseline_path = Path(args.baseline) if args.baseline else root / BASELINE_RELPATH
    if not baseline_path.is_file():
        print(f"check_design_tokens: baseline file not found: {baseline_path}", file=sys.stderr)
        return 2

    try:
        baseline = parse_baseline(baseline_path.read_text(encoding="utf-8"))
    except ScanError as exc:
        print(f"check_design_tokens: {exc}", file=sys.stderr)
        return 2

    ref_baseline = None
    if args.base_ref:
        try:
            ref_baseline = read_git_baseline(root, args.base_ref)
        except BaseRefError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2

    failures = compare(current, baseline, root)

    if ref_baseline is not None:
        failures.extend(compare_against_ref(baseline, ref_baseline))

    for line in failures:
        print(line)

    if failures:
        print(f"\n{len(failures)} design-token baseline violation(s).")
        return 1

    total = sum(current.values())
    print(
        f"design tokens: {len(current)} (path, rule) baseline entr(y/ies) match, "
        f"{total} total finding(s) across {len(files)} file(s)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
