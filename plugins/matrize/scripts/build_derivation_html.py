#!/usr/bin/env python3
"""Build the derivation-health Ledger — a static, print-first document.

Presentation class
------------------
A **Ledger**: a finite list of measured claims against fixed thresholds. Print-first, and
entirely static — no script at all.

That is not a simplification, it is the class's own test. Interactivity is warranted only
where an artefact has no readable static form, and the check is falsifiable: print it, and
if nothing is lost it should not have been interactive. Nothing is lost here. A finite
ledger also has a property most screens destroy — it is complete, and it ends. A reader
who can click no longer knows whether they have seen everything.

The pleasant consequence: the two independent XSS barriers a client-rendered viewer needs
collapse into something stronger than either, because there is no injection surface left.

Nor can it omit the appearance mode
-----------------------------------
`references/vocabulary/color-system.md` makes the mode a MANDATORY column, and says why: a
table mixing light-mode and dark-mode pairs "looks complete and is not -- it is the shape
of the error that hides a role behaving differently in the two modes". The first version of
this report's own fixture mixed `#FFFFFF` and `#0a0d10` backgrounds with no mode anywhere.

The fixture cannot state a contrast ratio
-----------------------------------------
Input colour pairs carry `fg` and `bg` only. Every ratio and every pass/fail flag is
COMPUTED here, and any ratio present in the input is rejected. Writing this the trusting
way once produced a demo claiming 2.98:1 for a pair that is 2.89:1 — the exact
asserted-rather-than-computed defect this report exists to catch, inside its own demo.

Usage:
    build_derivation_html.py --data FILE --out FILE [--tokens FILE]
    build_derivation_html.py --selftest
Exit: 0 built, 1 the input was unusable or carried a pre-stated ratio.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import chart as chartlib  # noqa: E402
import contrast  # noqa: E402
import vocabulary as vocablib  # noqa: E402

TEMPLATE = HERE.parent / "assets" / "derivation-viewer.html"
DEFAULT_TOKENS = HERE.parent / "assets" / "tokens.css"

TOKENS_MARKER = "<!--__DESIGN_TOKENS__-->"
MARKERS = {
    "verdict": "<!--__VERDICT__-->",
    "scope": "<!--__SCOPE__-->",
    "references": "<!--__REFERENCES__-->",
    "gradec": "<!--__GRADE_C__-->",
    "contrast": "<!--__CONTRAST__-->",
    "vocabulary": "<!--__VOCABULARY__-->",
}

REQUIRED = ("scope", "verdict", "references", "gradeCOnly", "contrast", "vocabulary")
# `</style`, in any casing. CSS treats `<\/style` as the same token sequence; HTML does not
# see a closing tag in it.
CLOSING_STYLE = re.compile(r"</(style)", re.IGNORECASE)
MODES = ("light", "dark", "forced")


def esc(text) -> str:
    return (str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def build_payload(data: dict) -> dict:
    missing = [k for k in REQUIRED if k not in data]
    if missing:
        raise ValueError(f"input is missing {', '.join(missing)}")

    pairs = []
    for entry in data["contrast"]:
        for stated in ("ratio", "passesAA", "passesAALarge"):
            if stated in entry:
                raise ValueError(
                    f"contrast entry for role {entry.get('role')!r} states {stated!r}. "
                    "Contrast is computed here, never supplied — remove it from the input."
                )
        if entry.get("mode") not in MODES:
            raise ValueError(
                f"contrast entry for role {entry.get('role')!r} states no appearance mode "
                f"(expected one of {', '.join(MODES)}). A contrast table that mixes light "
                f"and dark pairs without saying which is which looks complete and is not."
            )
        computed = contrast.verdict(contrast.ratio(entry["fg"], entry["bg"]))
        pairs.append({
            "role": entry["role"], "fg": entry["fg"], "bg": entry["bg"],
            "mode": entry["mode"],
            "ratio": computed["ratio"],
            "passesAA": computed["passesAA"],
            "passesAALarge": computed["passesAALarge"],
        })

    return {
        "scope": data["scope"], "verdict": data["verdict"],
        "references": data["references"], "gradeCOnly": data["gradeCOnly"],
        "contrast": pairs, "vocabulary": vocabulary_block(data["vocabulary"]),
    }


def vocabulary_block(declared: dict) -> dict:
    """What the system names, measured against the live registry rather than trusted.

    The input says which concepts the system uses; everything else here -- whether each
    one exists, which mandatory classes are uncovered, how large the vocabulary is -- is
    COMPUTED from references/vocabulary/. An input that asserted its own coverage would be
    the same defect as one asserting its own contrast ratio.
    """
    reg = vocablib.load()
    if reg.problems:
        raise ValueError("the vocabulary registry has problems: "
                         + "; ".join(reg.problems[:3]))
    named, unknown = [], []
    for entry in declared.get("terms", []):
        term, why = reg.lookup(vocablib.slug(entry["term"]), entry.get("dimension"))
        (named if term else unknown).append(term.display if term else f"{entry['term']} — {why}")
    covered = {vocablib.slug(c) for c in declared.get("assetClasses", [])}
    missing = [reg.classes[s].display for s in reg.mandatory
               if s not in covered and s in reg.classes]
    return {
        "total": len(reg.terms), "named": sorted(named), "unknown": sorted(unknown),
        "extensions": declared.get("extensions", []), "missingMandatory": missing,
    }


def references_table(rows: list[dict]) -> str:
    if not rows:
        return '<p class="empty">No references collected.</p>'
    body = "".join(
        "<tr>"
        f"<td>{esc(r['name'])}</td><td>{esc(r['method'])}</td>"
        f"<td class=\"grade grade-{esc(str(r['reliability']).lower())}\">{esc(r['reliability'])}</td>"
        f"<td>{esc(r['rights'])}</td><td class=\"num\">{esc(r['cards'])}</td>"
        "</tr>" for r in rows
    )
    return ("<table><thead><tr><th>Reference</th><th>Method</th><th>Reliability</th>"
            f"<th>Rights</th><th>Cards</th></tr></thead><tbody>{body}</tbody></table>")


def gradec_table(rows: list[dict]) -> str:
    if not rows:
        return ('<p class="empty">None — every token rests on at least one grade-A or '
                'grade-B source.</p>')
    body = "".join(
        "<tr>"
        f"<td>{esc(r['token'])}</td><td>{esc(r['reference'])}</td>"
        f"<td>{esc(r['wouldSet'])}</td><td class=\"blocking\">blocked</td>"
        "</tr>" for r in rows
    )
    return ("<table><thead><tr><th>Token</th><th>Reference</th>"
            "<th>What it would have set</th><th>Status</th></tr></thead>"
            f"<tbody>{body}</tbody></table>")


def contrast_block(pairs: list[dict]) -> str:
    """The chart carries the margin; the table carries the exact values. Never both for
    the same fact — the table prints the ratio, the chart shows the distance to the rule."""
    if not pairs:
        return '<p class="empty">No colour pairs to check.</p>'
    svg = chartlib.render(
        chartlib.contrast_chart([{"role": p["role"], "ratio": p["ratio"]} for p in pairs]),
        width=720,
    )
    # R2 — no number is printed twice. The chart already prints each ratio (that printed
    # value is what keeps colour from being its only channel), so the table carries the
    # pair and the verdicts and NOT the ratio. A first draft had both, which is the rule
    # broken in the very report that grades other people's rules.
    body = "".join(
        "<tr>"
        f"<td>{esc(p['role'])}</td><td>{esc(p['fg'])} on {esc(p['bg'])}</td>"
        f"<td class=\"mode mode-{esc(p['mode'])}\">{esc(p['mode'])}</td>"
        f"<td{'' if p['passesAA'] else ' class=\"blocking\"'}>"
        f"{'passes' if p['passesAA'] else 'FAILS'}</td>"
        f"<td{'' if p['passesAALarge'] else ' class=\"blocking\"'}>"
        f"{'passes' if p['passesAALarge'] else 'FAILS'}</td>"
        "</tr>" for p in pairs
    )
    # The mode column is mandatory, per color-system.md. Without it this very table mixes
    # a white-background pair with three dark-background ones and reads as one population.
    table = ("<table><thead><tr><th>Role</th><th>Pair</th><th>Mode</th>"
             "<th>Body text (AA 4.5)</th><th>Large text (AA 3.0)</th></tr></thead>"
             f"<tbody>{body}</tbody></table>")
    return f"<figure>{svg}</figure>{table}"


def vocabulary_table(block: dict) -> str:
    rows = []
    for display in block["named"]:
        rows.append(f"<tr><td>{esc(display)}</td><td>vocabulary</td><td>—</td></tr>")
    for entry in block["extensions"]:
        rows.append(
            f"<tr><td>{esc(entry['term'])}</td>"
            f"<td class=\"extension\">declared extension</td>"
            f"<td>{esc(entry.get('why', ''))} "
            f"({esc(entry.get('card', 'no card'))})</td></tr>")
    for text in block["unknown"]:
        rows.append(f"<tr><td>{esc(text)}</td><td class=\"blocking\">unknown</td>"
                    f"<td>neither a vocabulary term nor a declared extension</td></tr>")
    if not rows:
        return '<p class="empty">This system names no concepts at all.</p>'
    table = ("<table><thead><tr><th>Concept</th><th>Standing</th><th>Note</th></tr></thead>"
             f"<tbody>{''.join(rows)}</tbody></table>")
    if block["missingMandatory"]:
        items = "".join(f"<li>{esc(name)}</li>" for name in block["missingMandatory"])
        table += ('<p class="note blocking">Mandatory asset classes with no coverage:</p>'
                  f'<ul class="gaps">{items}</ul>')
    else:
        table += ('<p class="note">Every mandatory asset class is covered.</p>')
    return table


def render(payload: dict, tokens_path: Path) -> str:
    template = TEMPLATE.read_text(encoding="utf-8")
    for marker in (TOKENS_MARKER, *MARKERS.values()):
        if marker not in template:
            raise ValueError(f"template has no {marker}")

    # House convention: the marker is REPLACED by a whole <style> block, rather than
    # sitting inside one. Matching it means a builder and a template from two different
    # plugins stay interchangeable.
    # The Ledger's whole claim is that it has no injection surface because it has no
    # script. That holds only if the injected CSS cannot close its own element: a token
    # value is a string the validator does not constrain (fontFamily is "any string"), and
    # HTML closes a raw-text element case-INSENSITIVELY, so `</StYlE>` would end the block
    # and everything after it becomes markup.
    css = CLOSING_STYLE.sub(r"<\\/\1", tokens_path.read_text(encoding="utf-8"))
    out = template.replace(TOKENS_MARKER, "<style>\n" + css + "\n</style>", 1)
    out = out.replace(MARKERS["verdict"], esc(payload["verdict"]), 1)
    out = out.replace(MARKERS["scope"], esc(payload["scope"]), 1)
    out = out.replace(MARKERS["references"], references_table(payload["references"]), 1)
    out = out.replace(MARKERS["gradec"], gradec_table(payload["gradeCOnly"]), 1)
    out = out.replace(MARKERS["contrast"], contrast_block(payload["contrast"]), 1)
    out = out.replace(MARKERS["vocabulary"], vocabulary_table(payload["vocabulary"]), 1)
    return out


def selftest() -> int:
    sample = {
        "scope": "s", "verdict": "v", "references": [],
        "gradeCOnly": [],
        "contrast": [{"role": "dominant-action", "fg": "#FA2E1A", "bg": "#FFFFFF",
                      "mode": "light"}],
        "vocabulary": {
            "terms": [{"term": "Action / interactive", "dimension": "color-system"}],
            "extensions": [{"term": "Density bias", "why": "no term for it",
                            "card": "CARD-031"}],
            "assetClasses": ["Open Graph image"],
        },
    }
    checks: list[tuple[str, bool]] = []

    got = build_payload(sample)["contrast"][0]
    checks.append(("computes the ratio",
                   got["ratio"] == 3.84 and not got["passesAA"] and got["passesAALarge"]))

    modeless = json.loads(json.dumps(sample))
    modeless["contrast"][0].pop("mode")
    try:
        build_payload(modeless)
        checks.append(("refuses a contrast pair with no appearance mode", False))
    except ValueError:
        checks.append(("refuses a contrast pair with no appearance mode", True))

    lying = json.loads(json.dumps(sample))
    lying["contrast"][0]["ratio"] = 9.99
    try:
        build_payload(lying)
        checks.append(("refuses a pre-stated ratio", False))
    except ValueError:
        checks.append(("refuses a pre-stated ratio", True))

    for key in REQUIRED:
        broken = json.loads(json.dumps(sample))
        broken.pop(key)
        try:
            build_payload(broken)
            checks.append((f"refuses input missing {key}", False))
        except ValueError:
            pass
    checks.append(("refuses incomplete input", True))

    page = render(build_payload(sample), DEFAULT_TOKENS)
    checks.append(("no script element at all — nothing to inject into",
                   "<script" not in page))
    checks.append(("print rules are present", "@page" in page and "@media print" in page))
    checks.append(("tokens marker replaced by a whole <style> block",
                   TOKENS_MARKER not in page and page.count("<style>") >= 2))
    checks.append(("every content marker filled",
                   not any(m in page for m in MARKERS.values())))
    checks.append(("the chart primitive is embedded, server-rendered",
                   'class="chart"' in page and "<svg" in page))
    checks.append(("the verdict is static markup", 'class="verdict"' in page))

    nasty = json.loads(json.dumps(sample))
    nasty["verdict"] = "</style><img src=x onerror=alert(1)>"
    page2 = render(build_payload(nasty), DEFAULT_TOKENS)
    # What matters is that no TAG survives, not that a scary substring is absent:
    # `onerror=alert(1)` between escaped angle brackets is inert text, and asserting its
    # absence would be over-strict — a test failing on safe output teaches nothing.
    checks.append(("markup in content cannot form a tag",
                   "&lt;/style&gt;" in page2 and "<img" not in page2
                   and "&lt;img src=x onerror=alert(1)&gt;" in page2))

    # R2, asserted rather than trusted: each ratio appears exactly once in the document.
    multi = {**sample, "contrast": [
        {"role": "a", "fg": "#FA2E1A", "bg": "#FFFFFF", "mode": "light"},
        {"role": "b", "fg": "#8b9aa4", "bg": "#0a0d10", "mode": "dark"},
    ]}
    # Scoped to what a reader actually SEES. The injected tokens.css carries its own
    # measured ratios in a header comment — 6.73:1 among them — and counting those as
    # "printed twice" would fail on a coincidence between the demo colours and the
    # stylesheet's documentation. R2 is about the report, not about invisible comments.
    page3 = render(build_payload(multi), DEFAULT_TOKENS)
    visible = page3.split("</style>")[-1]
    checks.append(("no ratio is printed twice in the report body (R2)",
                   visible.count("3.84") == 1 and visible.count("6.73") == 1))

    # The vocabulary block is COMPUTED against the live registry, never trusted.
    block = build_payload(sample)["vocabulary"]
    checks.append(("a named concept is resolved against the real registry",
                   block["named"] == ["Action / interactive"] and not block["unknown"]))
    checks.append(("a declared extension is shown as such, not as a term",
                   len(block["extensions"]) == 1 and not block["unknown"]))
    checks.append(("uncovered mandatory classes are computed, not supplied",
                   set(block["missingMandatory"]) ==
                   {"Empty state illustration", "Error state illustration"}))
    made_up = json.loads(json.dumps(sample))
    made_up["vocabulary"]["terms"] = [{"term": "Vibe", "dimension": "color-system"}]
    checks.append(("a concept the vocabulary does not name is reported, not accepted",
                   build_payload(made_up)["vocabulary"]["unknown"] != []))
    checks.append(("the mode is rendered as a word, not only as a colour",
                   ">light<" in page and 'class="mode' in page))

    # The Ledger's class claim is "no script, therefore no injection surface". That holds
    # only if the injected token CSS cannot close its own <style> -- and HTML closes a
    # raw-text element case-insensitively, so a lowercase-only replace is not enough.
    import tempfile
    for variant in ("</style>", "</StYlE>", "</SCRIPT></style>"):
        tf = tempfile.NamedTemporaryFile("w", suffix=".css", delete=False, encoding="utf-8")
        tf.write(f':root {{ --font-sans: "{variant}<img src=x onerror=alert(1)>"; }}\n')
        tf.close()
        injected = render(build_payload(sample), Path(tf.name))
        # An injected closer shows up as one more </style> than there are <style>.
        opens = len(re.findall(r"<style\b", injected, re.IGNORECASE))
        closers = len(re.findall(r"</style\b", injected, re.IGNORECASE))
        checks.append((f"token CSS cannot close its own <style> ({variant})",
                       opens == closers))
        Path(tf.name).unlink()

    checks.append(("deterministic", render(build_payload(sample), DEFAULT_TOKENS) == page))

    for label, ok in checks:
        print(f"  {label:<52} {'ok' if ok else 'FAIL'}")
    bad = sum(1 for _, ok in checks if not ok)
    print(f"\n{len(checks)} check(s), {bad} failure(s)")
    print("RED" if bad else "GREEN")
    return 1 if bad else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("--data", help="decode-run JSON")
    ap.add_argument("--out", help="output HTML path")
    ap.add_argument("--tokens", default=str(DEFAULT_TOKENS),
                    help="design tokens CSS to inject (house convention: an argument, "
                         "not a hardcoded path)")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        return selftest()
    if not args.data or not args.out:
        ap.print_help()
        return 1

    try:
        data = json.loads(Path(args.data).read_text(encoding="utf-8"))
        page = render(build_payload(data), Path(args.tokens))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"build_derivation_html.py: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    Path(args.out).write_text(page, encoding="utf-8")
    print(f"wrote {args.out} ({len(page):,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
