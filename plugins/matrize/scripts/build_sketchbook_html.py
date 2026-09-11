#!/usr/bin/env python3
"""Render the design sketchbook — the Specimen, print-first, landscape A4.

Format
------
Measured off the reference artefact rather than invented: landscape A4 at **root-2**
(1.414), a 66/34 split between a rounded specimen canvas and an `ANMERKUNGEN` margin,
numbered callouts in two weights (FILLED pins the artwork, OUTLINED opens the margin
entry), a tinted observation box for the derived note, and a hairline footer carrying
`NN / TT — block name`.

Note the reference uses 1.414, not the 16:10 a generic landscape scaffold assumes. Its
pages carry /Rotate 90 over a portrait MediaBox, so reading the MediaBox alone says
portrait and is wrong.

Two modes
---------
**approval** (default) is the reference's shape: no code anywhere, because it goes in
front of a decision-maker, and it carries the approval block.
**handoff** adds a bottom-anchored implementation snippet per working spread plus the
inlined implementation plan, which is what a developer needs and a client does not.

Text into illustration
----------------------
A UX-law obligation, not a flourish: prose past its slot budget stops being read
(Cognitive Load, Miller's Law). An ANMERKUNG over budget is rendered as a do/don't
figure instead — but ONLY when the entry carries a structured `rule` and `antiRule` to
draw. With nothing to draw, it flags the overrun and leaves the prose alone. Inventing
a figure the lexicon never described is the same defect as a rule with no card behind it.

Usage:
    build_sketchbook_html.py --data FILE --out FILE [--mode approval|handoff]
    build_sketchbook_html.py --selftest
Exit: 0 built, 1 unusable input.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import chart as chartlib  # noqa: E402
import gradients as gradlib  # noqa: E402
import icons as iconlib  # noqa: E402
import contrast as contrastlib  # noqa: E402

TEMPLATE = HERE.parent / "assets" / "sketchbook-template.html"
TOKENS = HERE.parent / "assets" / "tokens.css"

# Character budget per ANMERKUNG. Past this the entry becomes a figure — see the
# module docstring for why this is a rule rather than a preference.
NOTE_BUDGET = 240


def esc(text) -> str:
    return (str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def do_dont_figure(rule: str, anti: str) -> str:
    """A two-panel do/don't figure. Draws only what it was given."""
    return f"""<figure class="figure">
<svg viewBox="0 0 300 92" role="img" aria-label="{esc(rule)} — not: {esc(anti)}">
  <rect x="1" y="1" width="144" height="66" rx="10" fill="none" stroke="#1a1a1a" stroke-width="1.2"/>
  <circle cx="22" cy="22" r="7" fill="#1a1a1a"/>
  <rect x="36" y="17" width="92" height="5" rx="2.5" fill="#1a1a1a" opacity=".75"/>
  <rect x="16" y="40" width="70" height="16" rx="8" fill="#d4321e"/>
  <rect x="94" y="40" width="34" height="16" rx="8" fill="none" stroke="#bdb7af" stroke-width="1.2"/>
  <text x="73" y="84" text-anchor="middle" font-size="10" fill="#1a1a1a" font-weight="600">so</text>

  <rect x="155" y="1" width="144" height="66" rx="10" fill="none" stroke="#d4321e"
        stroke-width="1.2" stroke-dasharray="4,3"/>
  <circle cx="176" cy="22" r="7" fill="#1a1a1a"/>
  <rect x="190" y="17" width="92" height="5" rx="2.5" fill="#1a1a1a" opacity=".75"/>
  <rect x="170" y="40" width="70" height="16" rx="8" fill="#d4321e"/>
  <rect x="248" y="40" width="34" height="16" rx="8" fill="#d4321e"/>
  <line x1="163" y1="9" x2="291" y2="59" stroke="#d4321e" stroke-width="1.2" opacity=".55"/>
  <text x="227" y="84" text-anchor="middle" font-size="10" fill="#d4321e" font-weight="600">nicht</text>
</svg>
<figcaption>{esc(rule)} — <b>nicht:</b> {esc(anti)}</figcaption>
</figure>"""


def render_note(note: dict, index: int | None) -> str:
    """One ANMERKUNG. Over budget with a structured pair -> figure; otherwise flagged."""
    text = note.get("text", "")
    rule, anti = note.get("rule"), note.get("antiRule")
    num = (f'<span class="note-num">{index}</span>' if index else
           '<span class="note-num" aria-hidden="true"></span>' if False else "")

    over = len(text) > NOTE_BUDGET
    if over and rule and anti:
        inner = do_dont_figure(rule, anti)
    elif over:
        inner = (f"<p>{esc(text)}</p>"
                 f'<p class="budget-flag">{len(text)} characters against a {NOTE_BUDGET} '
                 f"budget, and no structured rule/anti-rule pair to draw. Shorten it, or "
                 f"give the lexicon entry a rule and an anti-rule.</p>")
    else:
        inner = f"<p>{esc(text)}</p>"
        if anti:
            inner += f'<span class="anti"><b>nicht:</b> {esc(anti)}</span>'
    return f'<div class="note">{num}<div>{inner}</div></div>'


def spread(kind: str, kicker: str, title: str, canvas: str, notes: list[dict],
           observation: str, page: int, total: int, label: str,
           snippet: str | None, plain: bool = False) -> str:
    numbered = any(n.get("pin") for n in notes)
    note_html = "".join(
        render_note(n, (i + 1) if numbered else None) for i, n in enumerate(notes)
    )
    obs = f'<div class="observation">{esc(observation)}</div>' if observation else ""
    canvas_cls = "canvas canvas--plain" if plain else "canvas"
    snip = ""
    if snippet:
        snip = f"<pre>{esc(snippet)}</pre>"
    return f"""<section class="spread spread--{kind}">
  <p class="kicker">{esc(kicker)}</p>
  <h1>{esc(title)}</h1>
  <div class="body">
    <div class="{canvas_cls}">{canvas}</div>
    <aside class="anmerkungen"><h2>Anmerkungen</h2>{note_html}{obs}</aside>
  </div>
  {snip}
  <footer><span>{esc(label)}</span><span>{page:02d} / {total:02d} — {esc(title)}</span></footer>
</section>"""


def colour_canvas(colours: list[dict]) -> str:
    chips = []
    for c in colours:
        v = contrastlib.verdict(contrastlib.ratio(c["hex"], c.get("on", "#ffffff")))
        mark = "passes AA" if v["passesAA"] else ("large text only" if v["passesAALarge"] else "fails AA")
        chips.append(
            f'<div class="chip"><div class="sw" style="background:{esc(c["hex"])}"></div>'
            f'<div class="nm">{esc(c["name"])}</div>'
            f'<div class="vl">{esc(c["hex"])}</div>'
            f'<div class="cr">{v["ratio"]}:1 — {mark}</div></div>'
        )
    return f'<div class="chips">{"".join(chips)}</div>'


def type_canvas(steps: list[dict]) -> str:
    rows = []
    for s in steps:
        rows.append(
            f'<div class="row"><p class="eyebrow">{esc(s["label"])}</p>'
            f'<div style="font-size:{s["px"]}px;line-height:1.15">{esc(s["specimen"])}</div></div>'
        )
    return "".join(rows)


def icons_canvas(c: dict) -> str:
    """Seeds at the design size, one at a reduced size to show optical stroke, and the
    keylines they were drawn against — the system, not a contact sheet."""
    system = iconlib.IconSystem(base=c.get("base", 4))
    names = c.get("names") or list(iconlib.SEEDS)
    cells = "".join(
        f'<div class="icon-cell">{iconlib.render(n, system=system)}'
        f'<div class="icon-name">{esc(iconlib.naming(n))}</div>'
        f'<div class="icon-key">{esc(iconlib.SEEDS[n]["keyline"])}</div></div>'
        for n in names if n in iconlib.SEEDS
    )
    small = "".join(
        f'<div class="icon-cell">{iconlib.render("search", size=px, system=system)}'
        f'<div class="icon-key">{px:g}px · stroke {system.optical_stroke(px):g}</div></div>'
        for px in (system.grid, system.grid * 2 / 3, system.grid / 2)
    )
    return (f'<div class="icon-grid">{cells}</div>'
            f'<p class="eyebrow" style="margin-top:1.1rem">Optische Grösse</p>'
            f'<div class="icon-grid">{small}</div>')


def gradient_canvas(c: dict) -> str:
    """Derived gradients, each shown as the real blend beside the roles it came from."""
    roles = c["roles"]
    derived = gradlib.derive(roles)
    if not derived:
        return '<p class="empty">Keine Rolle stützt einen Verlauf. Das ist ein Befund.</p>'
    cards = []
    for name, tok in derived.items():
        ends = [roles[st["color"].strip("{}").split(".", 1)[-1]] for st in tok["$value"]]
        chain = " → ".join(st["color"].strip("{}").split(".", 1)[-1] for st in tok["$value"])
        cards.append(
            f'<div class="grad"><div class="grad-sw" style="background:linear-gradient('
            f'90deg,{ends[0]},{ends[-1]})"></div>'
            f'<div class="nm">{esc(name)}</div><div class="vl">{esc(chain)}</div></div>'
        )
    return f'<div class="grads">{"".join(cards)}</div>'


def states_canvas(states: list[dict]) -> str:
    cells = []
    for s in states:
        cls = {"default": "btn", "ghost": "btn btn--ghost", "disabled": "btn btn--disabled",
               "focus": "btn btn--focus"}.get(s["kind"], "btn")
        cells.append(f'<div><div class="{cls}">{esc(s["text"])}</div>'
                     f'<div class="state-label">{esc(s["kind"])}</div></div>')
    return f'<div class="states">{"".join(cells)}</div>'


def build(data: dict, mode: str = "approval") -> str:
    template = TEMPLATE.read_text(encoding="utf-8")
    system = data.get("system", "Design System")
    label = data.get("footerLabel", system)
    spreads_in = data.get("spreads", [])
    handoff = mode == "handoff"

    # cover + the working spreads + approval
    total = len(spreads_in) + 2
    out: list[str] = []

    out.append(f"""<section class="spread spread--statement">
  <div class="statement-body">
    <p class="kicker">{esc(data.get('kicker', 'Sketchbook'))}</p>
    <h1>{esc(system)}</h1>
    <p class="lede">{esc(data.get('philosophy', ''))}</p>
  </div>
  <footer><span>{esc(label)}</span><span>01 / {total:02d}</span></footer>
</section>""")

    for i, sp in enumerate(spreads_in, start=2):
        kind = sp.get("canvas", {}).get("kind", "")
        c = sp.get("canvas", {})
        if kind == "colour":
            canvas = colour_canvas(c["colours"])
        elif kind == "type":
            canvas = type_canvas(c["steps"])
        elif kind == "states":
            canvas = states_canvas(c["states"])
        elif kind == "icons":
            canvas = icons_canvas(c)
        elif kind == "gradient":
            canvas = gradient_canvas(c)
        elif kind == "contrast":
            # Computed here, never supplied. A hand-typed ratio in a fixture is exactly
            # the "asserted rather than computed" defect this spread exists to expose,
            # and the first draft of this demo carried four of them.
            pairs = []
            for pr in c["pairs"]:
                if "ratio" in pr:
                    raise ValueError(
                        f"contrast pair {pr.get('role')!r} states a ratio. Give fg and bg; "
                        "the ratio is computed."
                    )
                pairs.append({
                    "role": pr["role"],
                    "ratio": contrastlib.verdict(contrastlib.ratio(pr["fg"], pr["bg"]))["ratio"],
                    "mode": pr.get("mode", ""),
                    "unproven": pr.get("unproven", False),
                })
            canvas = chartlib.render(chartlib.contrast_chart(pairs), width=700)
        elif kind == "motion":
            canvas = chartlib.render(chartlib.motion_chart(c["durations"]), width=700)
        elif kind == "spacing":
            canvas = chartlib.render(chartlib.spacing_chart(c["steps"], c["base"]), width=700)
        elif kind == "scale":
            canvas = chartlib.render(chartlib.scale_chart(c["steps"], c["intended"]), width=700)
        else:
            canvas = f'<p class="empty">{esc(c.get("text", "No specimen for this block."))}</p>'
        out.append(spread(
            "working", data.get("kicker", "Sketchbook"), sp["title"], canvas,
            sp.get("notes", []), sp.get("observation", ""), i, total, label,
            sp.get("snippet") if handoff else None,
            plain=kind in ("type", "contrast", "motion", "spacing", "scale"),
        ))

    gate = data.get("approval", {})
    out.append(f"""<section class="spread spread--statement">
  <div class="statement-body">
    <p class="kicker">{esc(data.get('kicker', 'Sketchbook'))}</p>
    <div class="approval">
    <h2>{esc(gate.get('framing', 'Diskussionsgrundlage, kein fertiges Regelwerk.'))}</h2>
    <p>{esc(gate.get('criteria', ''))}</p>
    <p class="line">Entscheider: <span class="rule-line">{esc(gate.get('decisionMaker', ''))}</span></p>
    <p class="line">Freigegeben: <span class="rule-line"></span> Datum: <span class="rule-line" style="min-width:8rem"></span></p>
    <p class="line">Freigabe umfasst: {esc(gate.get('covers', 'Richtung | Richtung und Taxonomie | das ganze System'))}</p>
    </div>
  </div>
  <footer><span>{esc(label)}</span><span>{total:02d} / {total:02d} — Freigabe</span></footer>
</section>""")

    controls = ('<button id="md-export" class="md-export-btn">Export as Markdown</button>'
                if handoff else "")
    md = ""
    if handoff and data.get("markdown"):
        md = ('<script type="text/plain" id="md-source">'
              + data["markdown"].replace("</script", "<\\/script") + "</script>")

    page = template.replace("<!--__TITLE__-->", esc(f"{system} — Sketchbook"))
    page = page.replace("<!--__DESIGN_TOKENS__-->", "")   # the Specimen carries its own
    page = page.replace("<!--__CONTROLS__-->", controls)
    page = page.replace("<!--__SPREADS__-->", "\n".join(out))
    page = page.replace("<!--__MD_SOURCE__-->", md)
    return page


DEMO = {
    "system": "Beispielsystem",
    "kicker": "Sketchbook — Neues Designkonzept",
    "footerLabel": "Beispielsystem — Design Sketchbook",
    "philosophy": "Eine dominante Aktionsfarbe, ein weiches Radius-System, drei Register.",
    "spreads": [{
        "title": "Farbe",
        "canvas": {"kind": "colour", "colours": [
            {"name": "Aktion", "hex": "#FA2E1A", "on": "#ffffff"},
            {"name": "Tinte", "hex": "#1a1a1a", "on": "#ffffff"},
        ]},
        "notes": [{"text": "Rot bleibt die einzige dominante Aktionsfarbe pro View.",
                   "antiRule": "nie zwei gleichzeitig", "pin": True}],
        "observation": "Der Ball im Schriftzug liefert das Gold-Motiv bereits.",
        "snippet": "--action: #FA2E1A;",
    }],
    "approval": {"framing": "Diskussionsgrundlage, kein fertiges Regelwerk.",
                 "criteria": "Rückmeldung zu Farbe und Templates vor der Produktion.",
                 "decisionMaker": "", "covers": "Richtung"},
    "markdown": "# Beispielsystem\n",
}


def selftest() -> int:
    checks: list[tuple[str, bool]] = []
    page = build(DEMO)
    checks.append(("landscape A4 in @page", "size: A4 landscape" in page))
    checks.append(("root-2 aspect, not 16/10", "aspect-ratio: 1.414" in page and "16 / 10" not in page))
    checks.append(("cover is a statement spread", 'spread--statement' in page))
    checks.append(("approval block is present by default", "Diskussionsgrundlage" in page))
    checks.append(("approval mode carries NO code", "<pre>" not in page))
    # The BUTTON must be absent. The string "md-export" also appears in the stylesheet
    # and in the listener's own guard, so a bare substring test asserts the wrong thing.
    checks.append(("no markdown-export BUTTON in approval mode",
                   '<button id="md-export"' not in page))
    checks.append(("contrast is computed into the chip", "3.84:1" in page))
    checks.append(("footer numbers the block", "01 / 03" in page))

    hand = build(DEMO, mode="handoff")
    checks.append(("handoff mode adds the snippet", "<pre>" in hand))
    checks.append(("handoff mode adds the export control", 'id="md-export"' in hand))

    # A stated ratio must be refused, not quietly trusted.
    lying = json.loads(json.dumps(DEMO))
    lying["spreads"] = [{"title": "K", "canvas": {"kind": "contrast",
                        "pairs": [{"role": "r", "ratio": 9.99}]}, "notes": []}]
    try:
        build(lying)
        checks.append(("a stated contrast ratio is refused", False))
    except ValueError:
        checks.append(("a stated contrast ratio is refused", True))

    computed = json.loads(json.dumps(DEMO))
    computed["spreads"] = [{"title": "K", "canvas": {"kind": "contrast",
                           "pairs": [{"role": "r", "fg": "#FA2E1A", "bg": "#ffffff"}]},
                           "notes": []}]
    checks.append(("fg/bg is computed into the chart", "3.84:1" in build(computed)))

    # text -> illustration
    long_with_pair = {"text": "x" * 300, "rule": "Eine Aktionsfarbe", "antiRule": "nie zwei"}
    long_without = {"text": "y" * 300}
    short = {"text": "kurz"}
    checks.append(("over budget + a pair -> figure", "<figure" in render_note(long_with_pair, 1)))
    checks.append(("over budget, nothing to draw -> flagged, prose kept",
                   "budget-flag" in render_note(long_without, 1)
                   and "<figure" not in render_note(long_without, 1)))
    checks.append(("under budget -> plain prose", "<figure" not in render_note(short, 1)))
    checks.append(("markup in a note is escaped",
                   "&lt;script&gt;" in render_note({"text": "<script>"}, 1)))

    for label, ok in checks:
        print(f"  {label:<48} {'ok' if ok else 'FAIL'}")
    bad = sum(1 for _, ok in checks if not ok)
    print(f"\n{len(checks)} check(s), {bad} failure(s)")
    print("RED" if bad else "GREEN")
    return 1 if bad else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("--data")
    ap.add_argument("--out")
    ap.add_argument("--mode", choices=("approval", "handoff"), default="approval")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        return selftest()
    if not args.data or not args.out:
        ap.print_help()
        return 1
    try:
        data = json.loads(Path(args.data).read_text(encoding="utf-8"))
        page = build(data, args.mode)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"build_sketchbook_html.py: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    Path(args.out).write_text(page, encoding="utf-8")
    print(f"wrote {args.out} ({len(page):,} bytes, mode={args.mode})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
