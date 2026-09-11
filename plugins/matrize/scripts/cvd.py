#!/usr/bin/env python3
"""Colour-vision-deficiency separation for a categorical palette — measured, not argued.

Why this exists
---------------
"Can this palette carry eight categories?" is usually settled by taste. It is decidable:
simulate each colour under dichromatic vision and measure the perceptual distance between
the closest pair. If the worst pair is indistinguishable under deuteranopia, the palette
does not carry eight categories, however many hexes it has.

The metric is not chosen here — it is the one this workshop's own token file already
names for exactly this purpose: **CIEDE2000 under a Viénot-Brettel-Mollon (1999)
dichromat simulation**.

Calibration
-----------
CIEDE2000 has famously easy-to-get-wrong branches: the hue-difference wrap, the
arctangent quadrant, and the RT rotation term. `--selftest` checks the implementation
against pairs from the Sharma-Wu-Dalal published test set, which exists precisely because
so many implementations are subtly wrong. An implementation that passes its own examples
and fails those is not a metric.

Usage:
    cvd.py --palette "#5b7fa6,#7a9e6b,…"   worst pair, per vision type
    cvd.py --tokens tokens.css --prefix --cat-   pull a scale out of a CSS file
    cvd.py --selftest
Exit: 0 ok, 1 the selftest failed.
"""

from __future__ import annotations

import argparse
import math
import re
import sys
from itertools import combinations
from pathlib import Path

# A common rule of thumb for "two category colours are telling apart": dE00 below this
# and a reader working under that deficiency cannot reliably separate them. Stated as a
# threshold to check against, never as a measurement taken.
SEPARATION_FLOOR = 10.0


def srgb_to_linear(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def hex_to_rgb(value: str) -> tuple[float, float, float]:
    v = value.strip().lstrip("#")
    if len(v) == 3:
        v = "".join(ch * 2 for ch in v)
    return tuple(int(v[i:i + 2], 16) / 255 for i in (0, 2, 4))  # type: ignore[return-value]


def rgb_to_xyz(rgb: tuple[float, float, float]) -> tuple[float, float, float]:
    r, g, b = (srgb_to_linear(c) for c in rgb)
    return (
        0.4124564 * r + 0.3575761 * g + 0.1804375 * b,
        0.2126729 * r + 0.7151522 * g + 0.0721750 * b,
        0.0193339 * r + 0.1191920 * g + 0.9503041 * b,
    )


def xyz_to_lab(xyz: tuple[float, float, float]) -> tuple[float, float, float]:
    # D65 white
    xn, yn, zn = 0.95047, 1.0, 1.08883
    def f(t: float) -> float:
        return t ** (1 / 3) if t > 216 / 24389 else (24389 / 27 * t + 16) / 116
    fx, fy, fz = f(xyz[0] / xn), f(xyz[1] / yn), f(xyz[2] / zn)
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))


def lab(value: str) -> tuple[float, float, float]:
    return xyz_to_lab(rgb_to_xyz(hex_to_rgb(value)))


def ciede2000(l1: tuple[float, float, float], l2: tuple[float, float, float]) -> float:
    """CIEDE2000. Branch-heavy on purpose; the selftest is what makes it trustworthy."""
    L1, a1, b1 = l1
    L2, a2, b2 = l2
    kL = kC = kH = 1.0

    C1 = math.hypot(a1, b1)
    C2 = math.hypot(a2, b2)
    Cbar = (C1 + C2) / 2
    G = 0.5 * (1 - math.sqrt(Cbar ** 7 / (Cbar ** 7 + 25 ** 7))) if Cbar > 0 else 0.5
    a1p, a2p = (1 + G) * a1, (1 + G) * a2
    C1p, C2p = math.hypot(a1p, b1), math.hypot(a2p, b2)

    def hp(ap: float, bp: float) -> float:
        if ap == 0 and bp == 0:
            return 0.0
        h = math.degrees(math.atan2(bp, ap))
        return h + 360 if h < 0 else h

    h1p, h2p = hp(a1p, b1), hp(a2p, b2)

    dLp = L2 - L1
    dCp = C2p - C1p

    if C1p * C2p == 0:
        dhp = 0.0
    elif abs(h2p - h1p) <= 180:
        dhp = h2p - h1p
    elif h2p - h1p > 180:
        dhp = h2p - h1p - 360
    else:
        dhp = h2p - h1p + 360
    dHp = 2 * math.sqrt(C1p * C2p) * math.sin(math.radians(dhp) / 2)

    Lbarp = (L1 + L2) / 2
    Cbarp = (C1p + C2p) / 2
    if C1p * C2p == 0:
        hbarp = h1p + h2p
    elif abs(h1p - h2p) <= 180:
        hbarp = (h1p + h2p) / 2
    elif h1p + h2p < 360:
        hbarp = (h1p + h2p + 360) / 2
    else:
        hbarp = (h1p + h2p - 360) / 2

    T = (1
         - 0.17 * math.cos(math.radians(hbarp - 30))
         + 0.24 * math.cos(math.radians(2 * hbarp))
         + 0.32 * math.cos(math.radians(3 * hbarp + 6))
         - 0.20 * math.cos(math.radians(4 * hbarp - 63)))
    dtheta = 30 * math.exp(-(((hbarp - 275) / 25) ** 2))
    RC = 2 * math.sqrt(Cbarp ** 7 / (Cbarp ** 7 + 25 ** 7)) if Cbarp > 0 else 0.0
    SL = 1 + (0.015 * (Lbarp - 50) ** 2) / math.sqrt(20 + (Lbarp - 50) ** 2)
    SC = 1 + 0.045 * Cbarp
    SH = 1 + 0.015 * Cbarp * T
    RT = -math.sin(math.radians(2 * dtheta)) * RC

    return math.sqrt(
        (dLp / (kL * SL)) ** 2
        + (dCp / (kC * SC)) ** 2
        + (dHp / (kH * SH)) ** 2
        + RT * (dCp / (kC * SC)) * (dHp / (kH * SH))
    )


# Viénot, Brettel & Mollon (1999) dichromat simulation, in LINEAR sRGB.
#
# The defining property, and the one the selftest checks: for a protanope and a
# deuteranope the R and G OUTPUT ROWS ARE IDENTICAL. That collapse is the deficiency —
# the two channels become one. A matrix whose R and G rows differ is not a dichromat
# simulation at all, and an earlier draft of this file had exactly that: red and green
# stayed 76% as far apart as normal vision, which should have been impossible.
#
# Tritanopia is deliberately absent. The Viénot single-plane approximation is derived for
# protan and deutan only; tritan needs Brettel's two-plane method, and shipping a
# protan-shaped matrix under a tritan label would be a claim the method cannot support.
# tokens.css names deuteranopia and protanopia, which is what this covers.
VIENOT = {
    "protanopia": (
        (0.11238, 0.88762, 0.0),
        (0.11238, 0.88762, 0.0),
        (0.00401, -0.00401, 1.0),
    ),
    "deuteranopia": (
        (0.29275, 0.70725, 0.0),
        (0.29275, 0.70725, 0.0),
        (-0.02234, 0.02234, 1.0),
    ),
}


def simulate(value: str, kind: str) -> str:
    if kind == "normal":
        return value
    m = VIENOT[kind]
    r, g, b = (srgb_to_linear(c) for c in hex_to_rgb(value))
    out = []
    for row in m:
        lin = max(0.0, min(1.0, row[0] * r + row[1] * g + row[2] * b))
        s = 12.92 * lin if lin <= 0.0031308 else 1.055 * lin ** (1 / 2.4) - 0.055
        out.append(round(max(0.0, min(1.0, s)) * 255))
    return "#%02x%02x%02x" % tuple(out)


def worst_pair(palette: list[str], kind: str) -> tuple[float, str, str]:
    worst = (999.0, "", "")
    for a, b in combinations(palette, 2):
        d = ciede2000(lab(simulate(a, kind)), lab(simulate(b, kind)))
        if d < worst[0]:
            worst = (d, a, b)
    return worst


def report(palette: list[str], label: str = "") -> dict:
    rows = {}
    for kind in ("normal", "deuteranopia", "protanopia"):
        d, a, b = worst_pair(palette, kind)
        rows[kind] = {"dE00": round(d, 2), "pair": (a, b), "clears": d >= SEPARATION_FLOOR}
    return {"label": label, "n": len(palette), "worst": rows}


def selftest() -> int:
    """Against the Sharma-Wu-Dalal published pairs, which exist to catch exactly the
    branch errors this function is full of."""
    # (Lab1, Lab2, expected dE00) — from the published CIEDE2000 test set.
    cases = [
        ((50.0000, 2.6772, -79.7751), (50.0000, 0.0000, -82.7485), 2.0425),
        ((50.0000, 3.1571, -77.2803), (50.0000, 0.0000, -82.7485), 2.8615),
        ((50.0000, 2.8361, -74.0200), (50.0000, 0.0000, -82.7485), 3.4412),
        ((50.0000, -1.3802, -84.2814), (50.0000, 0.0000, -82.7485), 1.0000),
        ((50.0000, 2.5000, 0.0000), (73.0000, 25.0000, -18.0000), 27.1492),
        ((50.0000, 2.5000, 0.0000), (50.0000, 3.2972, 0.0000), 1.0000),
        ((50.0000, 2.5000, 0.0000), (50.0000, 1.8634, 0.5757), 1.0000),
        ((50.0000, 2.5000, 0.0000), (50.0000, 3.2592, 0.3350), 1.0000),
        ((50.0000, 2.5000, 0.0000), (50.0000, 3.1736, 0.5854), 1.0000),
        ((60.2574, -34.0099, 36.2677), (60.4626, -34.1751, 39.4387), 1.2644),
        ((22.7233, 20.0904, -46.6940), (23.0331, 14.9730, -42.5619), 2.0373),
        ((2.0776, 0.0795, -1.1350), (0.9033, -0.0636, -0.5514), 0.9082),
    ]
    # NOTE ON THE EVIDENCE. No independent CIEDE2000 implementation is installed here,
    # so these are transcribed constants and one of them was transcribed WRONG in the
    # first draft — attributing a 180-degree-hue pair's value to a 90-degree one. It was
    # removed rather than "corrected" to match this code's output, which would have made
    # the instrument agree with itself and prove nothing. What remains are pairs whose
    # values are structurally checkable: the four exactly-1.0000 pairs exist in the
    # literature precisely as calibration, and hitting them exactly exercises the G
    # factor, SC, SH and the hue branches.
    failures = 0
    for a, b, expected in cases:
        got = ciede2000(a, b)
        ok = abs(got - expected) < 0.0002
        failures += 0 if ok else 1
        if not ok:
            print(f"  FAIL dE00 {got:.4f}, expected {expected:.4f}")
    print(f"  CIEDE2000 vs {len(cases)} published pairs      "
          f"{'ok' if not failures else 'FAIL'}")

    checks: list[tuple[str, bool]] = []
    # sRGB -> Lab anchors that are fixed by definition.
    checks.append(("white is L*=100", abs(lab("#ffffff")[0] - 100) < 0.01))
    checks.append(("black is L*=0", abs(lab("#000000")[0]) < 0.01))
    checks.append(("identical colours are dE00 0",
                   ciede2000(lab("#4c8d5a"), lab("#4c8d5a")) < 1e-9))
    # Property, not a transcribed number: at equal chroma a 180-degree hue difference must
    # exceed a 90-degree one. True of the metric by construction, independent of any table.
    d90 = ciede2000((50, 2.5, 0), (50, 0, -2.5))
    d180 = ciede2000((50, 2.5, 0), (50, -2.5, 0))
    checks.append((f"180 deg hue beats 90 deg at equal chroma ({d180:.2f} > {d90:.2f})",
                   d180 > d90))

    # THE defining property of a dichromat simulation: R and G collapse into one channel.
    # An earlier matrix failed this silently, and the only symptom was red and green
    # staying 76% as distinguishable as normal — which is what sent me back to the matrix.
    for kind in ("deuteranopia", "protanopia"):
        rows = VIENOT[kind]
        checks.append((f"{kind}: R and G output rows are identical", rows[0] == rows[1]))

    # And the consequence, measured on an equiluminant pair so the test cannot be passed
    # by a lightness difference the simulation never touches.
    red, green = "#de2828", "#28843c"
    assert abs(lab(red)[0] - lab(green)[0]) < 1.0
    normal = ciede2000(lab(red), lab(green))
    deut = ciede2000(lab(simulate(red, "deuteranopia")), lab(simulate(green, "deuteranopia")))
    checks.append((f"equiluminant red/green collapses ({normal:.0f} -> {deut:.0f})",
                   deut < normal / 3))
    checks.append(("simulation leaves 'normal' untouched",
                   simulate("#4c8d5a", "normal") == "#4c8d5a"))

    for label, ok in checks:
        print(f"  {label:<52} {'ok' if ok else 'FAIL'}")
        failures += 0 if ok else 1

    print(f"\n{len(cases) + len(checks)} check(s), {failures} failure(s)")
    print("RED" if failures else "GREEN")
    return 1 if failures else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("--palette", help="comma-separated hex colours")
    ap.add_argument("--tokens", help="a CSS file to pull a scale out of")
    ap.add_argument("--prefix", default="--cat-", help="custom-property prefix to collect")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        return selftest()

    palette: list[str] = []
    if args.palette:
        palette = [c.strip() for c in args.palette.split(",") if c.strip()]
    elif args.tokens:
        text = Path(args.tokens).read_text(encoding="utf-8")
        # NOT anchored to line start: several viewers declare more than one custom
        # property per line, and an anchored pattern silently collects only the first —
        # which reported a six-role palette as three and would have understated the risk.
        decls = dict(re.findall(r"(--[\w-]+)\s*:\s*([^;{}]+);", text))
        for name, value in decls.items():
            if not name.startswith(args.prefix):
                continue
            v = value.strip()
            seen = set()
            while v.startswith("var(") and v not in seen:
                seen.add(v)
                v = decls.get(v[4:-1].strip(), v).strip()
            if re.fullmatch(r"#[0-9a-fA-F]{3,8}", v):
                palette.append(v)
    if len(palette) < 2:
        ap.print_help()
        return 1

    r = report(palette)
    print(f"{r['n']} colours; separation floor dE00 {SEPARATION_FLOOR:g}\n")
    for kind, row in r["worst"].items():
        mark = "clears" if row["clears"] else "BELOW FLOOR"
        print(f"  {kind:<14} worst pair {row['pair'][0]} / {row['pair'][1]}  "
              f"dE00 {row['dE00']:>6}  {mark}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
