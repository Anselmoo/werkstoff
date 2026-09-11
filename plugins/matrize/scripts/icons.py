#!/usr/bin/env python3
"""An icon SYSTEM — grid, keylines, stroke, optical sizing, naming — and 8-12 seed icons.

What this delivers, and what it does not
----------------------------------------
A system plus seeds, never a library. The growth rule is the deliverable: anyone can draw
icon 13 correctly because the grid, the keylines, the stroke and the naming are written
down and mechanically checked. Adopting an existing open set until a brand-owned one
exists is a first-class outcome here, not an admission — `placeholder_strategy()` says so
in as many words.

The grid is DERIVED, not decreed
---------------------------------
Grid = 6x the system's spacing base, live area 5x, padding 0.5x, stroke = base/2. With the
common 4px base that lands on the 24/20/2/2 convention Feather, Lucide and Tabler share —
so the derivation agrees with the ecosystem instead of fighting it, and a system with an
8px base gets a 48px grid without anyone re-deciding anything.

A brand mark is NOT an icon. A logo is drawn once at one size and may carry its own
geometry (this repo's own mark is 32-grid at 2.75 stroke, and stays outside this system).
An icon set is a system rendered at many sizes, so it needs uniform stroke and shared
keylines or it will not read as one family.

Every seed is defined as PRIMITIVES, not as a path string, so the same data both renders
and is checked. A declared coordinate list beside a hand-written `d` attribute is a lie
waiting to happen: the two drift and only the picture is real.

Usage:
    icons.py --list                 names and the keyline each one uses
    icons.py --svg check            one icon as SVG
    icons.py --sprite               every seed, as one SVG sheet
    icons.py --selftest             geometry is checked, not asserted
Exit: 0 ok, 1 a seed is off-grid or the selftest fails.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass

# --- the system ------------------------------------------------------------------


@dataclass
class IconSystem:
    base: float = 4.0           # the system's spacing base unit, in px

    @property
    def grid(self) -> float:
        return self.base * 6    # 24 at base 4

    @property
    def live(self) -> float:
        return self.base * 5    # 20 — the area an icon may actually occupy

    @property
    def pad(self) -> float:
        return self.base * 0.5  # 2

    @property
    def stroke(self) -> float:
        return self.base / 2    # 2

    @property
    def keylines(self) -> dict[str, tuple[float, float]]:
        """Shared shapes, so a square icon and a round icon read at the same weight.

        Optical, not geometric: a circle at the full live width reads smaller than a
        square at the full live width, so the square is inset and the circle is not.
        """
        return {
            "circle": (self.live, self.live),                  # 20 diameter
            "square": (self.live * 0.9, self.live * 0.9),      # 18 — inset optically
            "rect-portrait": (self.live * 0.8, self.live),     # 16 x 20
            "rect-landscape": (self.live, self.live * 0.8),    # 20 x 16
        }

    def optical_stroke(self, size: float) -> float:
        """Stroke at a rendered size. Below the design size it thickens relatively, or the
        icon dissolves; above it, it must not keep growing or the icon turns into a blob."""
        if size >= self.grid:
            return self.stroke
        return round(self.stroke * (self.grid / size) ** 0.5, 2)


SYSTEM = IconSystem()

# --- the seeds -------------------------------------------------------------------
# ("line", x1, y1, x2, y2) | ("circle", cx, cy, r) | ("poly", [(x, y), ...])
# | ("rect", x, y, w, h, rx)

SEEDS: dict[str, dict] = {
    "check":         {"keyline": "square",        "parts": [("poly", [(5, 12.5), (10, 17.5), (19, 7)])]},
    "close":         {"keyline": "square",        "parts": [("line", 6, 6, 18, 18), ("line", 18, 6, 6, 18)]},
    "plus":          {"keyline": "square",        "parts": [("line", 12, 4, 12, 20), ("line", 4, 12, 20, 12)]},
    "menu":          {"keyline": "rect-landscape", "parts": [("line", 4, 7, 20, 7), ("line", 4, 12, 20, 12), ("line", 4, 17, 20, 17)]},
    "arrow-right":   {"keyline": "rect-landscape", "parts": [("line", 3.5, 12, 20, 12), ("poly", [(14, 6), (20, 12), (14, 18)])]},
    "chevron-down":  {"keyline": "rect-landscape", "parts": [("poly", [(6, 9.5), (12, 15.5), (18, 9.5)])]},
    "search":        {"keyline": "circle",        "parts": [("circle", 10.5, 10.5, 6.5), ("line", 15.5, 15.5, 20, 20)]},
    "clock":         {"keyline": "circle",        "parts": [("circle", 12, 12, 8.5), ("poly", [(12, 7), (12, 12), (16, 14)])]},
    "info":          {"keyline": "circle",        "parts": [("circle", 12, 12, 8.5), ("line", 12, 11.5, 12, 16.5), ("circle", 12, 8, 0.5)]},
    "user":          {"keyline": "square",        "parts": [("circle", 12, 8, 3.5), ("poly", [(5, 20), (5, 17), (8, 14), (16, 14), (19, 17), (19, 20)])]},
    "calendar":      {"keyline": "rect-portrait", "parts": [("rect", 3.5, 5, 17, 16, 2), ("line", 3.5, 10, 20.5, 10), ("line", 8, 2.5, 8, 7), ("line", 16, 2.5, 16, 7)]},
    "download":      {"keyline": "square",        "parts": [("line", 12, 3, 12, 15), ("poly", [(7.5, 10.5), (12, 15), (16.5, 10.5)]), ("poly", [(4, 18), (4, 21), (20, 21), (20, 18)])]},
}


def coords(parts: list) -> list[tuple[float, float]]:
    """Every extreme point a primitive touches. Circles contribute their bounding box."""
    out: list[tuple[float, float]] = []
    for p in parts:
        if p[0] == "line":
            out += [(p[1], p[2]), (p[3], p[4])]
        elif p[0] == "circle":
            cx, cy, r = p[1], p[2], p[3]
            out += [(cx - r, cy - r), (cx + r, cy + r)]
        elif p[0] == "poly":
            out += list(p[1])
        elif p[0] == "rect":
            out += [(p[1], p[2]), (p[1] + p[3], p[2] + p[4])]
    return out


def render(name: str, size: float | None = None, system: IconSystem = SYSTEM) -> str:
    seed = SEEDS[name]
    g = system.grid
    size = size or g
    sw = system.optical_stroke(size)
    body: list[str] = []
    for p in seed["parts"]:
        if p[0] == "line":
            body.append(f'<line x1="{p[1]}" y1="{p[2]}" x2="{p[3]}" y2="{p[4]}"/>')
        elif p[0] == "circle":
            fill = ' fill="currentColor"' if p[3] <= 1 else ""
            body.append(f'<circle cx="{p[1]}" cy="{p[2]}" r="{p[3]}"{fill}/>')
        elif p[0] == "poly":
            pts = " ".join(f"{x},{y}" for x, y in p[1])
            body.append(f'<polyline points="{pts}"/>')
        elif p[0] == "rect":
            body.append(f'<rect x="{p[1]}" y="{p[2]}" width="{p[3]}" height="{p[4]}" rx="{p[5]}"/>')
    return (
        f'<svg class="icon icon-{name}" viewBox="0 0 {g:g} {g:g}" width="{size:g}" '
        f'height="{size:g}" fill="none" stroke="currentColor" stroke-width="{sw:g}" '
        f'stroke-linecap="round" stroke-linejoin="round" role="img" '
        f'aria-label="{name}">{"".join(body)}</svg>'
    )


def naming(name: str, mode: str = "") -> str:
    """`icon-<name>` and `icon-<name>~dark`. The tilde marks an APPEARANCE variant, not a
    different icon — so a build can strip it and still resolve the family."""
    return f"icon-{name}~{mode}" if mode else f"icon-{name}"


def growth_rule(system: IconSystem = SYSTEM) -> str:
    return (
        f"Draw on a {system.grid:g} grid inside a {system.live:g} live area "
        f"({system.pad:g} padding all round). Stroke {system.stroke:g}, round caps and "
        f"joins, no fills except a dot under {system.base / 4:g}px radius. Snap every "
        f"point to a {system.base / 8:g} subdivision. Pick one of the four keylines and "
        f"fill it — an icon that sits inside no keyline will read a different size from "
        f"its neighbours. Name it icon-<noun>, and ~dark only when the appearance mode "
        f"genuinely needs different geometry, never merely a different colour."
    )


def placeholder_strategy() -> str:
    return (
        "Until a brand-owned set exists, adopt one open family wholesale — Feather, Lucide "
        "or Tabler, all MIT and all already on a 24 grid at 2 stroke, which is this "
        "system's derived geometry. Adopt ONE: mixing two families is visible immediately "
        "at the terminals. Record the choice and its licence as a reference with its "
        "rights grade, exactly like any other. This is a first-class outcome, not a gap."
    )


# --- the instrument --------------------------------------------------------------


def validate(system: IconSystem = SYSTEM) -> list[str]:
    """Geometry is CHECKED, not asserted. A stated grid nothing verifies is a wish."""
    problems: list[str] = []
    lo, hi = system.pad, system.grid - system.pad
    sub = system.base / 8  # 0.5 at base 4
    for name, seed in SEEDS.items():
        if seed["keyline"] not in system.keylines:
            problems.append(f"{name}: keyline {seed['keyline']!r} is not one of the four")
        for x, y in coords(seed["parts"]):
            if not (lo - 1e-9 <= x <= hi + 1e-9) or not (lo - 1e-9 <= y <= hi + 1e-9):
                problems.append(
                    f"{name}: point ({x}, {y}) is outside the live area [{lo:g}, {hi:g}]"
                )
            for v, axis in ((x, "x"), (y, "y")):
                if abs(round(v / sub) * sub - v) > 1e-9:
                    problems.append(f"{name}: {axis}={v} is off the {sub:g} subdivision")
    return problems


def selftest() -> int:
    checks: list[tuple[str, bool]] = []
    problems = validate()
    checks.append((f"all {len(SEEDS)} seeds sit on the grid", not problems))
    for p in problems[:8]:
        print(f"    {p}")

    checks.append(("8-12 seeds, a system not a library", 8 <= len(SEEDS) <= 12))
    checks.append(("every seed names one of the four keylines",
                   all(s["keyline"] in SYSTEM.keylines for s in SEEDS.values())))

    # The validator must actually FAIL on bad geometry, or it is decoration.
    import copy

    def sabotage(parts) -> bool:
        """Plant one bad primitive, ask the validator, and put back a FRESH deep copy.

        Restoring with `SEEDS.update(saved)` shares the inner dicts, so the next sabotage
        mutates the saved copy too and the restore silently puts the damage back. The test
        caught exactly that.
        """
        pristine = copy.deepcopy(SEEDS)
        SEEDS["check"]["parts"] = parts
        caught = bool(validate())
        SEEDS.clear()
        SEEDS.update(copy.deepcopy(pristine))
        return caught

    checks.append(("an off-grid point is caught",
                   sabotage([("poly", [(0.5, 12.5), (10, 17.5), (19, 7)])])))
    checks.append(("an off-subdivision point is caught",
                   sabotage([("poly", [(5.3, 12.5), (10, 17.5), (19, 7)])])))
    checks.append(("a bad keyline is caught",
                   (lambda: (SEEDS["check"].__setitem__("keyline", "blob"),
                             bool(validate()),
                             SEEDS["check"].__setitem__("keyline", "square"))[1])()))
    checks.append(("restored clean after every sabotage", not validate()))

    # Derivation, not decree.
    checks.append(("base 4 derives the 24/20/2/2 convention",
                   (SYSTEM.grid, SYSTEM.live, SYSTEM.pad, SYSTEM.stroke) == (24, 20, 2, 2)))
    big = IconSystem(base=8)
    checks.append(("base 8 derives a 48 grid without re-deciding",
                   (big.grid, big.live, big.stroke) == (48, 40, 4)))

    # Optical sizing must actually change with size, and must not run away.
    checks.append(("stroke thickens below the design size",
                   SYSTEM.optical_stroke(16) > SYSTEM.stroke))
    checks.append(("stroke does not keep growing above it",
                   SYSTEM.optical_stroke(48) == SYSTEM.stroke))

    checks.append(("naming carries the ~dark appearance variant",
                   naming("check", "dark") == "icon-check~dark"))
    svg = render("search")
    checks.append(("renders stroke-only with round terminals",
                   'fill="none"' in svg and 'stroke-linecap="round"' in svg))
    checks.append(("renders an accessible label", 'aria-label="search"' in svg))

    for label, ok in checks:
        print(f"  {label:<48} {'ok' if ok else 'FAIL'}")
    bad = sum(1 for _, ok in checks if not ok)
    print(f"\n{len(checks)} check(s), {bad} failure(s)")
    print("RED" if bad else "GREEN")
    return 1 if bad else 0


def sprite() -> str:
    cells = "".join(
        f'<div style="text-align:center"><div>{render(n)}</div>'
        f'<div style="font-size:9px;margin-top:4px">{n}</div></div>'
        for n in SEEDS
    )
    return f'<div style="display:grid;grid-template-columns:repeat(6,1fr);gap:14px">{cells}</div>'


def main() -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--svg")
    ap.add_argument("--sprite", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        return selftest()
    if args.list:
        print(growth_rule(), "\n")
        for n, s in SEEDS.items():
            print(f"  {naming(n):<20} keyline={s['keyline']}")
        print("\n" + placeholder_strategy())
        return 0
    if args.svg:
        if args.svg not in SEEDS:
            print(f"no seed named {args.svg!r}", file=sys.stderr)
            return 1
        print(render(args.svg))
        return 0
    if args.sprite:
        print(sprite())
        return 0
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
