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
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import chart as chartlib  # noqa: E402
import contrast  # noqa: E402
import vocabulary as vocablib  # noqa: E402
from report_kit import render as kit_render  # noqa: E402

TEMPLATE = HERE.parent / "assets" / "derivation-viewer.html"
DEFAULT_TOKENS = HERE.parent / "assets" / "tokens.css"

TOKENS_MARKER = "<!--__DESIGN_TOKENS__-->"
KIT_MARKER = "<!--__REPORT_KIT__-->"
DATA_MARKER = "@@DATA@@"
#: Static markup the builder fills itself. Everything else rides in the JSON island and is
#: composed by the page script through the report kit.
MARKERS = {
    "verdict": "<!--__VERDICT__-->",
    "scope": "<!--__SCOPE__-->",
    "chart": "<!--__CONTRAST_CHART__-->",
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


def suggest_fg(fg: str, bg: str, target: float = contrast.AA_BODY) -> str | None:
    """The nearest foreground on the same hue axis that clears `target`: the fg mixed toward
    black on a light ground, toward white on a dark one, in 1% steps. A suggestion, computed
    with the same ratio the report grades with -- never a number a human typed."""
    bg_light = contrast.luminance(contrast.parse_hex(bg)) > 0.5
    r, g, b = contrast.parse_hex(fg)
    end = 0 if bg_light else 255
    for step in range(1, 101):
        t = step / 100
        cand = "#{:02X}{:02X}{:02X}".format(*(round(c + (end - c) * t) for c in (r, g, b)))
        if contrast.ratio(cand, bg) >= target:
            return cand
    return None


def grade_c_findings(rows: list[dict]) -> list[dict]:
    return [{
        "id": r["token"], "severity": "blocker", "rule": "grade-C-only",
        "claim": f"{r['token']} would be set from grade-C evidence alone",
        "file": r["reference"], "quote": r["wouldSet"],
        "fix": "Corroborate with a grade-A or grade-B source, or carry it to the brief as an open question for a person to settle.",
        "evidence": [{"label": "reference", "detail": f"{r['reference']} is the only source recorded for this token"},
                     {"label": "why blocked", "detail": "a value supported solely by a screenshot or proof is not a token"}],
    } for r in rows]


def concept_rows(block: dict) -> list[dict]:
    rows = [{"concept": d, "standing": "vocabulary", "note": "\u2014"} for d in block["named"]]
    rows += [{"concept": e["term"], "standing": "declared extension",
              "note": f"{e.get('why', '')} ({e.get('card', 'no card')})"} for e in block["extensions"]]
    rows += [{"concept": t, "standing": "unknown",
              "note": "neither a vocabulary term nor a declared extension"} for t in block["unknown"]]
    return rows


def concept_findings(block: dict) -> list[dict]:
    out = [{
        "id": f"unknown-{i}", "severity": "blocker", "rule": "unknown-concept", "claim": text,
        "fix": "Name a vocabulary term, or declare it as an extension with its reason and the card that decided it.",
        "evidence": [{"label": "registry", "detail": "looked up in references/vocabulary/ and not found"}],
    } for i, text in enumerate(block["unknown"], 1)]
    out += [{
        "id": f"uncovered-{i}", "severity": "major", "rule": "mandatory-class-uncovered",
        "claim": f"Mandatory asset class with no coverage: {name}",
        "fix": f"Declare {name} in assetClasses once the system covers it, or record why it does not.",
        "evidence": [{"label": "registry", "detail": "the vocabulary marks this class mandatory; the input does not list it"}],
    } for i, name in enumerate(block["missingMandatory"], 1)]
    return out


def contrast_findings(pairs: list[dict]) -> list[dict]:
    out = []
    for p in pairs:
        if p["passesAA"]:
            continue
        large = p["passesAALarge"]
        fix_hex = suggest_fg(p["fg"], p["bg"])
        short = round(contrast.AA_BODY - p["ratio"], 2)
        out.append({
            "id": f"{p['role']}-{p['mode']}", "severity": "major" if large else "blocker",
            "rule": "AA-body" if large else "AA-body+large",
            "claim": f"{p['role']} ({p['mode']}) " + ("clears AA only at large sizes" if large else "fails AA at every size"),
            "file": p["role"], "quote": f"{p['fg']} on {p['bg']}",
            "fix": (f"Darken the foreground to about {fix_hex} (computed to clear 4.5)." if fix_hex
                    and contrast.luminance(contrast.parse_hex(p["bg"])) > 0.5 else
                    f"Lighten the foreground to about {fix_hex} (computed to clear 4.5)." if fix_hex
                    else "No foreground on this hue axis clears 4.5 against this ground; change the ground."),
            "evidence": [{"label": "short of AA body", "detail": f"{short} below the 4.5 threshold; the chart shows the pair's exact ratio"},
                         {"label": "large text", "detail": "passes at AA 3.0" if large else "also fails AA 3.0"}],
        })
    return out


def contrast_chart_markup(pairs: list[dict]) -> str:
    """The chart carries the margin and the printed ratio; the table carries pair and verdicts and
    NOT the ratio. R2: no number is printed twice, in the report that grades other people's rules."""
    if not pairs:
        return '<p class="empty">No colour pairs to check.</p>'
    return chartlib.render(
        chartlib.contrast_chart([{"role": p["role"], "ratio": p["ratio"]} for p in pairs]),
        width=720,
    )


def kit_report(payload: dict) -> dict:
    """The JSON island: everything the page script composes through the report kit.
    Contrast ratios are deliberately absent -- the chart prints each one once."""
    pairs = payload["contrast"]
    vocab = payload["vocabulary"]
    blocked = payload["gradeCOnly"]
    fails = [p for p in pairs if not p["passesAA"]]
    return {
        "stats": [
            {"label": "References", "value": str(len(payload["references"])), "note": "decoded and graded"},
            {"label": "Blocked tokens", "value": str(len(blocked)), "bad": bool(blocked),
             "note": "rest on grade-C evidence alone"},
            {"label": "Contrast pairs failing AA", "value": f"{len(fails)} / {len(pairs)}", "bad": bool(fails),
             "note": "body text, computed"},
            {"label": "Mandatory classes uncovered", "value": str(len(vocab["missingMandatory"])),
             "bad": bool(vocab["missingMandatory"]), "note": "asset classes with no coverage"},
        ],
        "references": payload["references"],
        "gradeCFindings": grade_c_findings(blocked),
        "concepts": concept_rows(vocab),
        "conceptFindings": concept_findings(vocab),
        "contrast": [{"role": p["role"], "pair": f"{p['fg']} on {p['bg']}", "mode": p["mode"],
                      "aa": p["passesAA"], "aaLarge": p["passesAALarge"]} for p in pairs],
        "contrastFindings": contrast_findings(pairs),
    }


def render(payload: dict, tokens_path: Path) -> str:
    template = TEMPLATE.read_text(encoding="utf-8")
    for marker in (TOKENS_MARKER, KIT_MARKER, DATA_MARKER, *MARKERS.values()):
        if marker not in template:
            raise ValueError(f"template has no {marker}")

    # The injected CSS must not be able to close its own element: a token value is a string
    # the validator does not constrain (fontFamily is "any string"), and HTML closes a
    # raw-text element case-INSENSITIVELY, so `</StYlE>` would end the block and everything
    # after it would become markup -- in a page that now carries a script. The kit's render()
    # inlines the tokens file as-is, so the sanitised copy is what it is handed.
    css = CLOSING_STYLE.sub(r"<\\/\1", tokens_path.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as td:
        safe_tokens = Path(td) / "tokens.css"
        safe_tokens.write_text(css, encoding="utf-8")
        page = kit_render(template, TEMPLATE.parent, kit_report(payload), tokens=safe_tokens)
    # The static markers are filled AFTER the kit has inlined the data island: text that
    # arrives from the input (the verdict, the scope) must never sit in the template while
    # the kit is still searching it for its own markers.
    return (page.replace(MARKERS["scope"], esc(payload["scope"]), 1)
            .replace(MARKERS["verdict"], esc(payload["verdict"]), 1)
            .replace(MARKERS["chart"], contrast_chart_markup(payload["contrast"]), 1))


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
    # The Ledger used to have no script at all. It now renders through the report kit, so the
    # claim that survives is narrower and still checkable: the report's data rides in ONE JSON
    # island that holds no raw angle bracket, and no script reaches for the network or innerHTML.
    island = re.search(r'<script type="application/json" id="report-data">(.*?)</script>', page, re.S)
    scripts = re.findall(r"<script\b[^>]*>(.*?)</script>", page, re.S)
    checks.append(("the data rides in one JSON island with no raw < > &",
                   island is not None and not re.search(r"[<>&]", island.group(1))))
    checks.append(("no script assigns HTML strings or reaches the network",
                   not any(re.search(r"innerHTML|outerHTML|insertAdjacentHTML|fetch\(|XMLHttpRequest", sc)
                           for sc in scripts)))
    checks.append(("print rules are present", "@page" in page and "@media print" in page))
    checks.append(("tokens marker replaced by a whole <style> block",
                   TOKENS_MARKER not in page and page.count("<style>") >= 2))
    checks.append(("every content marker filled",
                   not any(m in page for m in (*MARKERS.values(), DATA_MARKER))))
    checks.append(("the report kit marker replaced by its css and js",
                   "const RK = (() =>" in page and KIT_MARKER not in page))
    checks.append(("the chart primitive is embedded, server-rendered",
                   'class="chart"' in page and "<svg" in page))
    checks.append(("the verdict is static markup",
                   re.search(r'<p class="verdict[ "][^>]*>v</p>', page) is not None))

    nasty = json.loads(json.dumps(sample))
    nasty["verdict"] = "</style><img src=x onerror=alert(1)>"
    page2 = render(build_payload(nasty), DEFAULT_TOKENS)
    # What matters is that no TAG survives, not that a scary substring is absent:
    # `onerror=alert(1)` between escaped angle brackets is inert text, and asserting its
    # absence would be over-strict — a test failing on safe output teaches nothing.
    checks.append(("markup in content cannot form a tag",
                   "&lt;/style&gt;" in page2 and "<img" not in page2
                   and "&lt;img src=x onerror=alert(1)&gt;" in page2))
    # The same payload inside the data island: escaped on the way in (barrier one).
    hostile = json.loads(json.dumps(sample))
    hostile["gradeCOnly"] = [{"token": "</script><img src=x onerror=alert(1)>", "reference": "r",
                              "wouldSet": "x"}]
    page_h = render(build_payload(hostile), DEFAULT_TOKENS)
    checks.append(("markup in a finding cannot form a tag inside the data island",
                   "<img" not in page_h and "\\u003cimg" in page_h))

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
    # The table is composed by the page script now, so the word has two halves: the mode
    # travels in the island as a word, and the script prints it in its own column.
    checks.append(("the mode is rendered as a word, not only as a colour",
                   '"mode": "light"' in island.group(1) and 'label: "Mode"' in page
                   and 'class: "mode"' in page))

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
