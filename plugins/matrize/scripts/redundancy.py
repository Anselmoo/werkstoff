#!/usr/bin/env python3
"""Find categorical encodings carried by colour ALONE — the rule the numbers support.

Why this rule and not a hue count
----------------------------------
Measured with `cvd.py`, every categorical palette in this workshop falls below the
dichromacy separation floor — *including the shipped five-hue scale*, whose worst pair
sits at dE00 5.70 deuteranopia / 5.30 protanopia. Widening the cap does not fix that and
makes it monotonically worse: an eight-entry palette's worst pair measures 1.96.

So "how many hues may we have" is the wrong question. What carries the accessibility
claim is the rule the token file already states — **colour is never the only channel** —
and unlike a hue count, that is checkable.

Why a legend is not the answer
-------------------------------
A legend maps *name to hue*. Reading a chart requires the inverse: hue back to name. If
two hues are indistinguishable to the reader, the legend cannot be inverted and does not
rescue a colour-only cell. So redundancy is required **where the category is rendered**,
not somewhere else on the page.

What it detects, narrowly and on purpose
-----------------------------------------
Two patterns, both high-precision:

1. **Palette indexing** — an array of three or more colour literals selected by a
   computed key (`PALETTE[h % PALETTE.length]`). Categorical by construction.
2. **Colour-only sibling rules** — three or more CSS rules sharing a selector stem whose
   bodies set nothing but colour.

Anything else returns `undecided`, and `undecided` is never reported as a violation. A
detector that guesses costs more than one that abstains.

Usage:
    redundancy.py <file> [<file> ...]     one verdict per detected site
    redundancy.py --selftest
Exit: 0 no colour-only site, 1 at least one, 2 nothing could be read.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

COLOUR = r"(?:#[0-9a-fA-F]{3,8}|rgba?\([^)]*\)|hsla?\([^)]*\)|oklch\([^)]*\))"
COLOUR_PROPS = ("color", "background", "background-color", "fill", "stroke",
                "border-color", "outline-color")

# Non-colour channels that make a category readable without colour. Each is a real
# second encoding at the point of rendering, not a legend elsewhere.
REDUNDANCY_SIGNALS = (
    (re.compile(r"\btextContent\s*="), "a per-item text label"),
    (re.compile(r"\bcontent\s*:\s*[\"']"), "a CSS ::before/::after glyph"),
    (re.compile(r"\bstroke-dasharray\b"), "a dash pattern"),
    (re.compile(r"<pattern\b|url\(#"), "an SVG pattern fill"),
    (re.compile(r"\baria-label\s*="), "an accessible name"),
    (re.compile(r"\bsetAttribute\(\s*[\"'](?:d|points|r|width|height)[\"']"), "a varied shape"),
    (re.compile(r"\bmarker\b|\bsymbol\b"), "a marker glyph"),
    (re.compile(r"<span[^>]*>\s*\S[^<]*</span>"), "an adjacent text label"),
)

# How far from the colour assignment a redundant channel still counts as "at the point of
# rendering". Generous enough for a render function, tight enough that a legend 300 lines
# away does not count — which is the whole point.
PROXIMITY_LINES = 18


class Site:
    def __init__(self, kind: str, line: int, detail: str,
                 classes: tuple[str, ...] = ()) -> None:
        self.kind, self.line, self.detail = kind, line, detail
        self.classes = classes
        self.verdict = "undecided"
        self.evidence = ""

    def __str__(self) -> str:
        return (f"  line {self.line:>4}  {self.verdict:<12} {self.kind}: {self.detail}"
                + (f"  [{self.evidence}]" if self.evidence else ""))


def find_palette_indexing(text: str) -> list[Site]:
    sites: list[Site] = []
    for m in re.finditer(
        r"(?:const|let|var)\s+(\w+)\s*=\s*\[\s*((?:[\"']" + COLOUR + r"[\"']\s*,?\s*){3,})\]",
        text,
    ):
        name = m.group(1)
        count = len(re.findall(COLOUR, m.group(2)))
        # Only a violation if something INDEXES it by a computed key.
        indexed = re.search(re.escape(name) + r"\s*\[\s*[^\]]*%\s*", text)
        if not indexed:
            continue
        line = text[: m.start()].count("\n") + 1
        sites.append(Site("palette-index", line,
                          f"{name}[] of {count} colours selected by a computed key"))
    return sites


def find_colour_only_rules(text: str) -> list[Site]:
    """Three or more sibling rules whose bodies set nothing but colour."""
    stems: dict[str, list[tuple[int, str]]] = {}
    for m in re.finditer(r"(\.[\w-]+)(?:\.[\w-]+)*\s*\{([^}]*)\}", text):
        selector, body = m.group(1), m.group(2)
        decls = [d.strip() for d in body.split(";") if d.strip()]
        if not decls:
            continue
        props = [d.split(":", 1)[0].strip() for d in decls]
        if not all(p in COLOUR_PROPS for p in props):
            continue
        if not re.search(COLOUR + r"|var\(--", body):
            continue
        stem = re.sub(r"-?\d+$", "", selector).rstrip("-")
        line = text[: m.start()].count("\n") + 1
        stems.setdefault(stem, []).append((line, selector))
    sites: list[Site] = []
    for stem, members in stems.items():
        if len(members) >= 3:
            names = tuple(sel.lstrip(".") for _, sel in members)
            sites.append(Site("colour-only-rules", members[0][0],
                              f"{len(members)} sibling rules under {stem}* set colour and nothing else",
                              names))
    return sites


def redundancy_near(text: str, line: int) -> tuple[bool, str]:
    lines = text.splitlines()
    lo = max(0, line - 1 - PROXIMITY_LINES)
    hi = min(len(lines), line - 1 + PROXIMITY_LINES)
    window = "\n".join(lines[lo:hi])
    found = [label for pattern, label in REDUNDANCY_SIGNALS if pattern.search(window)]
    return (bool(found), ", ".join(found))


def use_sites(text: str, classes: tuple[str, ...]) -> list[int]:
    """Line numbers where these classes are actually applied in markup."""
    lines: list[int] = []
    for cls in classes:
        for m in re.finditer(r'class\s*=\s*["\'][^"\']*\b' + re.escape(cls) + r'\b', text):
            lines.append(text[: m.start()].count("\n") + 1)
    return sorted(set(lines))


def audit(text: str) -> list[Site]:
    sites = find_palette_indexing(text) + find_colour_only_rules(text)
    for site in sites:
        if site.classes:
            # A stylesheet is not where a category is rendered. Redundancy has to be
            # checked at the USE site — a first draft looked beside the CSS rule instead
            # and produced both a false positive (a legend whose glyphs sat 60 lines below
            # the rules) and a spurious pass (evidence borrowed from an unrelated rule).
            probes = use_sites(text, site.classes) or [site.line]
        else:
            probes = [site.line]
        hits = [redundancy_near(text, ln) for ln in probes]
        ok = any(h[0] for h in hits)
        site.verdict = "redundant" if ok else "COLOUR-ONLY"
        site.evidence = next((h[1] for h in hits if h[0]), "")
    return sites


CLEAN = """
const PALETTE = ['#5b7fa6', '#7a9e6b', '#c98f4a', '#a5648a'];
function draw(label, i) {
  var c = PALETTE[hash(label) % PALETTE.length];
  var node = make('circle');
  node.setAttribute('fill', c);
  var t = make('text');
  t.textContent = label;
}
"""

DIRTY = """
const PALETTE = ['#5b7fa6', '#7a9e6b', '#c98f4a', '#a5648a'];
function draw(label, i) {
  var c = PALETTE[hash(label) % PALETTE.length];
  var node = make('circle');
  node.setAttribute('fill', c);
}
"""

NOT_CATEGORICAL = """
const BRAND = ['#5b7fa6', '#7a9e6b', '#c98f4a'];
var header = BRAND[0];
"""

CSS_DIRTY = """
.cat-1 { background: #5b7fa6; }
.cat-2 { background: #7a9e6b; }
.cat-3 { background: #c98f4a; }
"""

CSS_CLEAN = """
.cat-1 { background: #5b7fa6; }
.cat-1::after { content: "A"; }
.cat-2 { background: #7a9e6b; }
.cat-3 { background: #c98f4a; }
"""

# Rules at the top, markup far below — the real shape of every viewer in this repo.
CSS_USED_WITH_LABEL = """
.sw-1 { background: #5b7fa6; }
.sw-2 { background: #7a9e6b; }
.sw-3 { background: #c98f4a; }
""" + "\n" * 60 + """
<li><span class="sw-1"></span><span class="name">alpha</span></li>
<li><span class="sw-2"></span><span class="name">beta</span></li>
<li><span class="sw-3"></span><span class="name">gamma</span></li>
"""

CSS_USED_BARE = """
.bw-1 { background: #5b7fa6; }
.bw-2 { background: #7a9e6b; }
.bw-3 { background: #c98f4a; }
""" + "\n" * 60 + """
<td class="bw-1"></td>
<td class="bw-2"></td>
<td class="bw-3"></td>
"""


def selftest() -> int:
    checks: list[tuple[str, bool]] = []

    dirty = audit(DIRTY)
    checks.append(("a hashed palette with no second channel is caught",
                   len(dirty) == 1 and dirty[0].verdict == "COLOUR-ONLY"))

    clean = audit(CLEAN)
    checks.append(("the same palette WITH a per-item label passes",
                   len(clean) == 1 and clean[0].verdict == "redundant"))
    checks.append(("and it names the channel it found",
                   "text label" in clean[0].evidence))

    checks.append(("a palette nobody indexes by a key is not categorical",
                   not find_palette_indexing(NOT_CATEGORICAL)))

    css_bad = audit(CSS_DIRTY)
    checks.append(("three colour-only sibling rules are caught",
                   any(s.verdict == "COLOUR-ONLY" for s in css_bad)))
    css_ok = audit(CSS_CLEAN)
    checks.append(("the same rules with a ::after glyph pass",
                   all(s.verdict == "redundant" for s in css_ok)))

    checks.append(("two sibling rules are below the threshold, not a finding",
                   not find_colour_only_rules(".cat-1{color:#111}.cat-2{color:#222}")))
    checks.append(("a rule that also sets a non-colour property is not colour-only",
                   not find_colour_only_rules(
                       ".c-1{color:#111;border-style:dashed}.c-2{color:#222;border-style:dotted}"
                       ".c-3{color:#333;border-style:solid}")))

    # Proximity is the rule: a legend far away must NOT rescue a colour-only site.
    far = DIRTY + "\n" * 60 + "<p class='legend'><span>alpha</span></p>"
    checks.append(("a legend 60 lines away does not count as redundancy",
                   audit(far)[0].verdict == "COLOUR-ONLY"))

    used_ok = audit(CSS_USED_WITH_LABEL)
    checks.append(("redundancy is found at the USE site, not the declaration",
                   all(s.verdict == "redundant" for s in used_ok)))
    used_bad = audit(CSS_USED_BARE)
    checks.append(("a bare swatch at the use site is still colour-only",
                   any(s.verdict == "COLOUR-ONLY" for s in used_bad)))

    checks.append(("empty input yields no findings", not audit("")))

    for label, ok in checks:
        print(f"  {label:<56} {'ok' if ok else 'FAIL'}")
    bad = sum(1 for _, ok in checks if not ok)
    print(f"\n{len(checks)} check(s), {bad} failure(s)")
    print("RED" if bad else "GREEN")
    return 1 if bad else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("files", nargs="*")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        return selftest()
    if not args.files:
        ap.print_help()
        return 2

    violations = 0
    for name in args.files:
        try:
            text = Path(name).read_text(encoding="utf-8")
        except OSError as exc:
            print(f"{name}: {exc}", file=sys.stderr)
            return 2
        sites = audit(text)
        print(f"\n{name}: {len(sites)} categorical site(s)")
        for site in sites:
            print(site)
            violations += site.verdict == "COLOUR-ONLY"
        if not sites:
            print("  no categorical colour encoding detected")
    print(f"\n{violations} colour-only site(s)")
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
