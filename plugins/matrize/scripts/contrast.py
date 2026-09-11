#!/usr/bin/env python3
"""Compute WCAG 2.x contrast ratios — because contrast is arithmetic, not an opinion.

Why this is a script and not an agent
-------------------------------------
A contrast ratio is fully determined by two colours. Asking a model to judge it produces
a number that looks like a measurement and is not one, and the whole point of separating
`decode` from `name` is that a reader can tell those apart. So this is computed, and a
value from here is never graded C — it is derived, not estimated.

It also de-subjectifies the colour conversation, which is most of its value in practice.
"That red feels hard to read" is arguable forever; "that red is 3.84:1 on white, which
passes AA for large text and fails it for body" ends the argument.

Usage:
    contrast.py "#FA2E1A" "#FFFFFF"              # one pair
    contrast.py --pairs pairs.json               # [["#fff","#000"], ...]
    contrast.py --css tokens.css --on "#0a0d10"  # every hex in a CSS file, on one bg
    contrast.py --selftest                       # verify against known published values
Exit: 0 always for a computation; 1 if --selftest fails or input cannot be parsed.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HEX = re.compile(r"#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})\b")

# WCAG 2.x thresholds. "Large" is >=18pt, or >=14pt bold.
AA_BODY = 4.5
AA_LARGE = 3.0
AAA_BODY = 7.0
AAA_LARGE = 4.5
# Non-text contrast (UI components, focus indicators, meaningful graphics).
NON_TEXT = 3.0


def parse_hex(value: str) -> tuple[int, int, int]:
    value = value.strip().lstrip("#")
    if len(value) == 3:
        value = "".join(c * 2 for c in value)
    if len(value) != 6:
        raise ValueError(f"not a hex colour: {value!r}")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def channel(component: int) -> float:
    """sRGB channel to linear light. The 0.03928 knee is the WCAG 2.x constant."""
    c = component / 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def luminance(rgb: tuple[int, int, int]) -> float:
    r, g, b = (channel(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def ratio(fg: str, bg: str) -> float:
    a, b = luminance(parse_hex(fg)), luminance(parse_hex(bg))
    lighter, darker = max(a, b), min(a, b)
    return (lighter + 0.05) / (darker + 0.05)


def verdict(value: float) -> dict:
    """What this ratio does and does not license. Never just a number.

    A bare ratio invites the reader to guess a threshold. Every caller wants the
    consequence, so the consequence is what is returned.
    """
    return {
        "ratio": round(value, 2),
        "passesAA": value >= AA_BODY,
        "passesAALarge": value >= AA_LARGE,
        "passesAAA": value >= AAA_BODY,
        "passesNonText": value >= NON_TEXT,
        "statement": statement(value),
    }


def statement(value: float) -> str:
    r = round(value, 2)
    if value >= AAA_BODY:
        return f"{r}:1 — passes AAA for body text."
    if value >= AA_BODY:
        return f"{r}:1 — passes AA for body text, fails AAA."
    if value >= AA_LARGE:
        return (
            f"{r}:1 — sufficient for large text and UI borders, "
            f"INSUFFICIENT for body text under AA ({AA_BODY}:1). "
            f"A button using this as body-size label text fails."
        )
    return f"{r}:1 — fails AA at every text size, and fails the {NON_TEXT}:1 non-text minimum."


def selftest() -> int:
    """Check against ratios that are fixed by the standard, not by this implementation.

    Calibrating the instrument before trusting its verdict: black-on-white is exactly
    21:1 and white-on-white exactly 1:1 by definition, so an implementation that gets
    either wrong is broken in a way no design review would catch.
    """
    # Every expectation below comes from OUTSIDE this file. Three are fixed by the
    # standard's own definition, two are published WCAG boundary examples, and four are
    # figures werkstoff's tools/design-tokens/tokens.css measured independently years
    # before this script existed. None was read off this implementation's output --
    # calibrating an instrument against its own results measures nothing.
    cases = [
        ("#000000", "#FFFFFF", 21.00),  # definitional maximum
        ("#FFFFFF", "#FFFFFF", 1.00),   # definitional minimum
        ("#000000", "#000000", 1.00),
        ("#777777", "#FFFFFF", 4.48),   # published: just under AA body
        ("#767676", "#FFFFFF", 4.54),   # published: just over
        ("#dfe6ea", "#0a0d10", 15.44),  # tokens.css --text
        ("#cdd8de", "#0a0d10", 13.43),  # tokens.css --smoke
        ("#8b9aa4", "#0a0d10", 6.73),   # tokens.css --muted
        ("#348ad9", "#0a0d10", 5.37),   # tokens.css --accent
    ]
    failures = 0
    for fg, bg, expected in cases:
        got = round(ratio(fg, bg), 2)
        ok = abs(got - expected) <= 0.02
        print(f"  {fg} on {bg}: {got:>6}:1  expected {expected:>6}:1  {'ok' if ok else 'FAIL'}")
        failures += 0 if ok else 1
    # The threshold boundary must actually discriminate, or the verdicts are decoration.
    if verdict(4.48)["passesAA"] or not verdict(4.54)["passesAA"]:
        print("  FAIL: the AA body threshold does not discriminate")
        failures += 1
    # The worked example is asserted on its CONSEQUENCE, not on a decimal: the claim that
    # matters is "large text yes, body text no", and that is what a reviewer acts on.
    worked = verdict(ratio("#FA2E1A", "#FFFFFF"))
    if worked["passesAA"] or not worked["passesAALarge"]:
        print(f"  FAIL: #FA2E1A on white should be large-text-only, got {worked['statement']}")
        failures += 1
    else:
        print(f"  #FA2E1A on #FFFFFF: {worked['ratio']}:1  large-text-only  ok")
    print(f"\n{len(cases)} case(s), {failures} failure(s)")
    print("RED" if failures else "GREEN")
    return 1 if failures else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("colours", nargs="*", help="foreground and background hex")
    ap.add_argument("--pairs", help="JSON file of [[fg, bg], ...]")
    ap.add_argument("--css", help="scan a CSS file for hex colours")
    ap.add_argument("--on", default="#FFFFFF", help="background for --css (default white)")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        return selftest()

    results = []
    try:
        if args.css:
            text = Path(args.css).read_text(encoding="utf-8")
            for hexval in sorted({m.group(0) for m in HEX.finditer(text)}):
                results.append({"fg": hexval, "bg": args.on, **verdict(ratio(hexval, args.on))})
        elif args.pairs:
            for fg, bg in json.loads(Path(args.pairs).read_text(encoding="utf-8")):
                results.append({"fg": fg, "bg": bg, **verdict(ratio(fg, bg))})
        elif len(args.colours) == 2:
            fg, bg = args.colours
            results.append({"fg": fg, "bg": bg, **verdict(ratio(fg, bg))})
        else:
            ap.print_help()
            return 1
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        print(f"contrast.py: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
