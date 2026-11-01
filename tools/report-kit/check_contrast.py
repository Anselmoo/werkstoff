#!/usr/bin/env python3
"""Measure every report-kit text role against every report-kit surface, dark and light.

usage: check_contrast.py [-h] [--tokens PATH] [--kit PATH] [--selftest]

Resolves the --rk-* role layer of report-kit.css (the dark :root block, then the
[data-theme="light"] block over it) through tools/design-tokens/tokens.css to hex, and
computes the WCAG 2.1 contrast of each TEXT role against each SURFACE role. A text role
is anything the kit or a viewer sets as the colour of small text; it must clear 4.5:1 on
--rk-bg, --rk-panel and --rk-panel-2 in both themes. The mark hues (--rk-ok, --rk-bad,
--rk-warn) are not text roles -- their text-safe twins (--rk-*-text) are.

Exit: 0 every pair clears 4.5:1; 1 a pair falls short; 2 a role or token did not resolve.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
TEXT_ROLES = ("--rk-text", "--rk-muted", "--rk-link", "--rk-flat", "--rk-ok-text", "--rk-bad-text", "--rk-warn-text")
SURFACES = ("--rk-bg", "--rk-panel", "--rk-panel-2")
FLOOR = 4.5

DECL = re.compile(r"(--[a-z0-9-]+)\s*:\s*([^;]+);")


def block(css: str, selector_re: str) -> str:
    """Body of the first rule whose selector matches selector_re (no nested braces)."""
    m = re.search(selector_re + r"\s*\{([^{}]*)\}", css)
    if not m:
        raise ValueError(f"no block matching {selector_re!r}")
    return m.group(1)


def decls(body: str) -> dict[str, str]:
    body = re.sub(r"/\*.*?\*/", "", body, flags=re.S)
    return {k: v.strip() for k, v in DECL.findall(body)}


def tokens(css: str) -> dict[str, str]:
    """Every custom property in tokens.css's top-level :root blocks (first value wins)."""
    out: dict[str, str] = {}
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    for body in re.findall(r"(?m)^:root\s*\{([^{}]*)\}", css):
        for k, v in decls(body).items():
            out.setdefault(k, v)
    return out


def resolve(name: str, scope: dict[str, str], depth: int = 0) -> str:
    if depth > 10 or name not in scope:
        raise KeyError(name)
    val = scope[name]
    m = re.fullmatch(r"var\((--[a-z0-9-]+)\)", val)
    return resolve(m.group(1), scope, depth + 1) if m else val


def luminance(hex_: str) -> float:
    h = hex_.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if not re.fullmatch(r"[0-9a-fA-F]{6}", h):
        raise ValueError(f"not a hex colour: {hex_}")
    def ch(i: int) -> float:
        c = int(h[i:i + 2], 16) / 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * ch(0) + 0.7152 * ch(2) + 0.0722 * ch(4)


def ratio(a: str, b: str) -> float:
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def themes(kit_css: str, tok: dict[str, str]) -> dict[str, dict[str, str]]:
    dark = decls(block(kit_css, r"(?m)^:root"))
    light = {**dark, **decls(block(kit_css, r'(?m)^:root\[data-theme="light"\]'))}
    # The OS-preference block must say the same as the toggle block (the kit's own rule).
    os_light = {**dark, **decls(block(kit_css, r':root:not\(\[data-theme="dark"\]\)'))}
    if os_light != light:
        diff = sorted(k for k in set(os_light) | set(light) if os_light.get(k) != light.get(k))
        raise ValueError(f"the two light blocks disagree on {', '.join(diff)}")
    return {"dark": {**tok, **dark}, "light": {**tok, **light}}


def measure(kit_css: str, tok_css: str) -> list[tuple[str, str, str, float]]:
    rows = []
    for theme, scope in themes(kit_css, tokens(tok_css)).items():
        for t in TEXT_ROLES:
            for s in SURFACES:
                rows.append((theme, t, s, ratio(resolve(t, scope), resolve(s, scope))))
    return rows


def report(rows: list[tuple[str, str, str, float]]) -> int:
    bad = [r for r in rows if r[3] < FLOOR]
    for theme, t, s, r in rows:
        mark = "FAIL" if r < FLOOR else "ok  "
        print(f"{mark} {theme:5} {t:15} on {s:12} {r:5.2f}:1")
    print(f"{len(rows) - len(bad)} of {len(rows)} text/surface pairs clear {FLOOR}:1")
    return 1 if bad else 0


def selftest(kit_css: str, tok_css: str) -> int:
    """Known answers, then planted defects that must each turn the check red."""
    failures = 0
    def expect(label: str, cond: bool) -> None:
        nonlocal failures
        print(("ok   " if cond else "FAIL ") + label)
        failures += not cond
    expect("white on black is 21:1", abs(ratio("#ffffff", "#000000") - 21) < 1e-9)
    expect("#777 on white is 4.48:1 (just under)", abs(ratio("#777777", "#ffffff") - 4.48) < 0.01)
    expect("the shipped kit passes", all(r[3] >= FLOOR for r in measure(kit_css, tok_css)))
    light_sel = ':root[data-theme="light"] {'
    planted = {
        # The defect the review found: --rk-flat never re-pointed in light (2.89:1 on white).
        "light --rk-flat left at --muted": lambda c: re.sub(r"(--rk-flat: var\(--muted-on-light\);)", "", c),
        # A status hue used as text: --status-warn as the warn text role (3.1:1 light).
        "light --rk-warn-text pointed at --status-warn": lambda c: c.replace("--rk-warn-text: var(--samaria-deep);", "--rk-warn-text: var(--status-warn);"),
        # A light block that forgets a text role entirely inherits the dark value.
        "light --rk-ok-text dropped": lambda c: c.replace("  --rk-ok-text: var(--chromia-deep);\n", "", 1)
            .replace("    --rk-ok-text: var(--chromia-deep);\n", "", 1),
    }
    for label, plant in planted.items():
        bad_css = plant(kit_css)
        expect(f"planted '{label}' changed the CSS", bad_css != kit_css)
        try:
            red = any(r[3] < FLOOR for r in measure(bad_css, tok_css))
        except (KeyError, ValueError):
            red = True
        expect(f"planted '{label}' turns the check red", red)
    # The light blocks drifting apart is itself an error.
    head, _, tail = kit_css.partition(light_sel)
    drift = head + light_sel + tail.replace("--rk-hit: var(--samaria-light);", "--rk-hit: var(--samaria);", 1)
    try:
        measure(drift, tok_css)
        expect("two disagreeing light blocks are refused", False)
    except ValueError:
        expect("two disagreeing light blocks are refused", True)
    print(f"selftest: {'PASS' if not failures else f'{failures} FAILED'}")
    return 1 if failures else 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="check_contrast.py", description=__doc__.split("\n\n")[0],
                                     epilog="exit 0 all clear, 1 a pair under 4.5:1, 2 unresolved role or token")
    parser.add_argument("--tokens", type=Path, default=ROOT / "tools/design-tokens/tokens.css")
    parser.add_argument("--kit", type=Path, default=HERE / "report-kit.css")
    parser.add_argument("--selftest", action="store_true", help="run known answers and planted defects")
    args = parser.parse_args(argv)
    kit_css = args.kit.read_text(encoding="utf-8")
    tok_css = args.tokens.read_text(encoding="utf-8")
    if args.selftest:
        return selftest(kit_css, tok_css)
    try:
        rows = measure(kit_css, tok_css)
    except (KeyError, ValueError) as err:
        print(f"unresolved: {err}", file=sys.stderr)
        return 2
    return report(rows)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
