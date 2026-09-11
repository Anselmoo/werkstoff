#!/usr/bin/env python3
"""One threshold-chart primitive, parameterised. Four call sites share this shape:

    measured value · log or linear axis · threshold rules · dot with a stem from the
    floor value · grouped by appearance mode

    contrast    ratio 1-21, log,    rules at 3.0 / 4.5 / 7.0
    motion      duration in ms,     linear, perception bounds
    type scale  deviation from the intended ratio, tolerance band
    spacing     deviation from the grid, zero or not zero

Three constraints, each with a reason rather than a preference:

* **Dot with a stem, not a bar.** A bar implies a meaningful zero. Contrast's floor is
  1.0, not 0, so a bar from zero misrepresents the quantity.
* **Log axis for ratios.** Linearly, a 15:1 pair consumes the axis and compresses the
  interesting 2.5-5 region into a sliver.
* **Colour is only ever redundant to position.** In an accessibility report anything else
  would be self-refuting, so every mark also carries a shape and a printed value.

What the chart adds over a table is **margin**. 3.84 against a 4.5 threshold is a near
miss fixed by darkening a few percent; 2.89 is a different colour. A table renders both
as the word "FAILS" and flattens a large difference in remediation cost.

Hand-rolled SVG on purpose: the vendored d3 subset ships neither d3-shape nor d3-axis, so
a d3 implementation would hand-write the path strings anyway — and this way a print-first
document carries no 125 KB dependency.

Usage:
    chart.py --selftest      # the thresholds must discriminate, or the chart is decoration
"""

from __future__ import annotations

import math
import sys
from dataclasses import dataclass, field

# Dash that already means "unproven" in three of this repo's viewers. Reused, not invented.
UNPROVEN_DASH = "4,3"


@dataclass
class Mark:
    label: str
    value: float
    mode: str = ""          # appearance mode: "", "light", "dark"
    note: str = ""          # printed beside the value
    unproven: bool = False  # grade-C provenance -> dashed stem


@dataclass
class Rule:
    at: float
    label: str
    kind: str = "pass"      # pass | warn | fail -- drives the dash pattern, not the colour


@dataclass
class Chart:
    title: str
    marks: list[Mark]
    rules: list[Rule] = field(default_factory=list)
    scale: str = "linear"   # linear | log
    domain: tuple[float, float] | None = None
    floor: float | None = None   # where stems start; defaults to the domain minimum
    unit: str = ""
    fmt: str = "{:.2f}"


ROW_H = 26
PAD_T = 34
PAD_B = 26
PAD_L = 190
PAD_R = 64


def _pos(value: float, lo: float, hi: float, scale: str, width: float) -> float:
    if scale == "log":
        lo_, hi_, v = math.log10(max(lo, 1e-9)), math.log10(max(hi, 1e-9)), math.log10(max(value, 1e-9))
    else:
        lo_, hi_, v = lo, hi, value
    if hi_ == lo_:
        return 0.0
    return (v - lo_) / (hi_ - lo_) * width


def _esc(text: str) -> str:
    return (str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def verdict(value: float, rules: list[Rule]) -> str:
    """Which band a value lands in. Position, not colour, is the primary channel."""
    passed = [r for r in rules if value >= r.at]
    if not passed:
        return "below every threshold"
    return max(passed, key=lambda r: r.at).label


def render(chart: Chart, width: int = 640) -> str:
    if not chart.marks:
        return '<p class="empty">No measurements for this dimension.</p>'

    values = [m.value for m in chart.marks] + [r.at for r in chart.rules]
    lo, hi = chart.domain if chart.domain else (min(values), max(values))
    if lo == hi:
        hi = lo + 1
    floor = chart.floor if chart.floor is not None else lo
    plot_w = width - PAD_L - PAD_R
    height = PAD_T + ROW_H * len(chart.marks) + PAD_B

    out: list[str] = [
        f'<svg class="chart" viewBox="0 0 {width} {height}" width="100%" '
        f'height="{height}" role="img" aria-label="{_esc(chart.title)}">'
    ]

    # threshold rules first, so marks sit above them
    for rule in chart.rules:
        x = PAD_L + _pos(rule.at, lo, hi, chart.scale, plot_w)
        dash = "" if rule.kind == "fail" else ' stroke-dasharray="2,3"'
        out.append(
            f'<line class="rule rule-{rule.kind}" x1="{x:.1f}" y1="{PAD_T - 14}" '
            f'x2="{x:.1f}" y2="{height - PAD_B + 4}"{dash}/>'
        )
        out.append(
            f'<text class="rule-label" x="{x:.1f}" y="{PAD_T - 20}" '
            f'text-anchor="middle">{_esc(rule.label)}</text>'
        )

    floor_x = PAD_L + _pos(floor, lo, hi, chart.scale, plot_w)

    for i, mark in enumerate(chart.marks):
        y = PAD_T + i * ROW_H + ROW_H / 2
        x = PAD_L + _pos(mark.value, lo, hi, chart.scale, plot_w)
        clears = all(mark.value >= r.at for r in chart.rules if r.kind == "pass") if chart.rules else True
        state = "clears" if clears else "short"
        dash = f' stroke-dasharray="{UNPROVEN_DASH}"' if mark.unproven else ""

        # Mode goes INLINE with the label. As a second line at y+9 it collided with the
        # next row's label at 26px row height — legible in isolation, unreadable stacked.
        label = f"{mark.label} ({mark.mode})" if mark.mode else mark.label
        out.append(
            f'<text class="mark-label" x="{PAD_L - 12}" y="{y:.1f}" text-anchor="end" '
            f'dominant-baseline="middle">{_esc(label)}</text>'
        )
        out.append(
            f'<line class="stem stem-{state}" x1="{floor_x:.1f}" y1="{y:.1f}" '
            f'x2="{x:.1f}" y2="{y:.1f}"{dash}/>'
        )
        # Shape is redundant to colour: a square head means it fell short of a threshold.
        if clears:
            out.append(f'<circle class="head head-clears" cx="{x:.1f}" cy="{y:.1f}" r="5"/>')
        else:
            out.append(
                f'<rect class="head head-short" x="{x - 5:.1f}" y="{y - 5:.1f}" '
                f'width="10" height="10"/>'
            )
        printed = chart.fmt.format(mark.value) + chart.unit
        out.append(
            f'<text class="mark-value" x="{x + 12:.1f}" y="{y:.1f}" '
            f'dominant-baseline="middle">{_esc(printed)}</text>'
        )

    out.append("</svg>")
    return "\n".join(out)


# --- the four call sites ---------------------------------------------------------

def contrast_chart(pairs: list[dict]) -> Chart:
    return Chart(
        title="Computed contrast",
        marks=[Mark(p["role"], p["ratio"], p.get("mode", ""), unproven=p.get("unproven", False))
               for p in pairs],
        rules=[Rule(3.0, "3.0 UI", "warn"), Rule(4.5, "4.5 AA body", "pass"),
               Rule(7.0, "7.0 AAA", "warn")],
        scale="log", domain=(1.0, 21.0), floor=1.0, unit=":1",
    )


def motion_chart(durations: list[dict]) -> Chart:
    return Chart(
        title="Motion duration",
        marks=[Mark(d["name"], d["ms"], d.get("mode", "")) for d in durations],
        rules=[Rule(100, "100 perceptible", "warn"), Rule(400, "400 Doherty", "fail")],
        scale="linear", domain=(0, 600), floor=0, unit="ms", fmt="{:.0f}",
    )


def scale_chart(steps: list[dict], intended: float, tolerance: float = 0.05) -> Chart:
    return Chart(
        title=f"Type scale — deviation from {intended}",
        marks=[Mark(s["name"], s["ratio"]) for s in steps],
        rules=[Rule(intended - tolerance, "−tol", "warn"),
               Rule(intended, "intended", "pass"),
               Rule(intended + tolerance, "+tol", "warn")],
        scale="linear",
        domain=(intended - tolerance * 4, intended + tolerance * 4),
        floor=intended, fmt="{:.3f}",
    )


def spacing_chart(steps: list[dict], base: float) -> Chart:
    return Chart(
        title=f"Spacing — multiples of {base:g}px",
        marks=[Mark(s["name"], s["px"] / base) for s in steps],
        rules=[Rule(1, "1×", "warn"), Rule(2, "2×", "warn"), Rule(4, "4×", "warn")],
        scale="linear", domain=(0, max([s["px"] / base for s in steps] + [4]) + 1),
        floor=0, unit="×", fmt="{:.2f}",
    )


def selftest() -> int:
    """A threshold that does not move the mark across the rule is decoration."""
    checks: list[tuple[str, bool]] = []

    c = contrast_chart([{"role": "a", "ratio": 4.49}, {"role": "b", "ratio": 4.51}])
    svg = render(c)
    checks.append(("4.49 gets a square head (fell short)", 'head-short' in svg))
    checks.append(("4.51 gets a circle head (clears)", 'head-clears' in svg))

    # The discriminating property: a hair either side of AA must land either side of the rule.
    lo, hi = 1.0, 21.0
    x_lo = _pos(4.49, lo, hi, "log", 500)
    x_rule = _pos(4.5, lo, hi, "log", 500)
    x_hi = _pos(4.51, lo, hi, "log", 500)
    checks.append(("marks straddle the 4.5 rule", x_lo < x_rule < x_hi))

    # Log actually spreads the interesting region. Linearly, 2.5-5 is a sliver.
    span_log = _pos(5, 1, 21, "log", 100) - _pos(2.5, 1, 21, "log", 100)
    span_lin = _pos(5, 1, 21, "linear", 100) - _pos(2.5, 1, 21, "linear", 100)
    checks.append(("log gives the 2.5-5 band more room than linear", span_log > span_lin * 1.5))

    checks.append(("stems start at the floor, not zero", f'x1="{PAD_L}.0"' in render(c)))
    checks.append(("grade-C provenance dashes the stem",
                   UNPROVEN_DASH in render(contrast_chart(
                       [{"role": "x", "ratio": 5, "unproven": True}]))))
    checks.append(("value is printed, so colour is never the only channel",
                   "4.49:1" in svg))
    checks.append(("empty input says so rather than drawing an empty frame",
                   "No measurements" in render(Chart("t", []))))
    checks.append(("markup is escaped",
                   "&lt;script&gt;" in render(Chart("t", [Mark("<script>", 2)]))))

    # All four call sites must produce something.
    for name, ch in (
        ("contrast", contrast_chart([{"role": "r", "ratio": 3}])),
        ("motion", motion_chart([{"name": "enter", "ms": 200}])),
        ("type scale", scale_chart([{"name": "h1", "ratio": 1.26}], 1.25)),
        ("spacing", spacing_chart([{"name": "s2", "px": 8}], 4)),
    ):
        checks.append((f"call site: {name}", render(ch).startswith("<svg")))

    for label, ok in checks:
        print(f"  {label:<52} {'ok' if ok else 'FAIL'}")
    bad = sum(1 for _, ok in checks if not ok)
    print(f"\n{len(checks)} check(s), {bad} failure(s)")
    print("RED" if bad else "GREEN")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(selftest() if "--selftest" in sys.argv else (print(__doc__) or 0))
