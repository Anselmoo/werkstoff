#!/usr/bin/env python3
"""Render assets/review-viewer.html from a nacharbeit review.

usage: build_review_html.py [-h] [--lint FILE] [--report FILE] [--calibration FILE] [--out FILE] [--selftest]

Findings by rule family, severity and FIX TIER. The tier column is the point: it
separates what a model can close from what is a judgement call, so a reader can
see the size of the remaining work rather than only its count. A family sitting
at 0/n is not evidence of health -- only that nothing exercised it.

  --lint         raw `nacharbeit_lint.py --format json` output; normalised here by collect(), which
                 keeps line, quote, suggested fix and angle, and derives the per-family totals from
                 the rubric
  --report       a report already in the viewer's shape
  --calibration  JSON {"planted", "fired", "blanked"} from test_nacharbeit_lint.py; without it the
                 page says plainly that the linter's calibration was not supplied

Exit: 0 written, 2 could not read an input.

STDLIB ONLY -- it must run under a bare system python3.
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from report_kit import KIT_MARKER, TOKENS_MARKER, render as kit_render  # noqa: E402

ASSETS = HERE.parent / "assets"
TEMPLATE = ASSETS / "review-viewer.html"
RUBRIC = HERE.parent / "references" / "rubric.md"
FIXTURE = HERE / "fixtures" / "review-demo.json"
MECHANICAL_FAMILIES = ("M", "H", "S", "A", "P", "D")


def to_record(f: dict) -> dict:
    """One finding in the viewer's shape -> the kit's finding record, nothing dropped."""
    rule = f.get("rule") or f.get("rule_id") or "?"
    family = f.get("family") or rule.split("-", 1)[0]
    tags = {"tier": f.get("tier") or f.get("fix_tier") or "sonnet", "family": family}
    if f.get("angle"):
        tags["angle"] = f["angle"]
    if f.get("plugin"):
        tags["plugin"] = f["plugin"]
    return {
        "id": f.get("id") or f"{rule}-{f.get('file', '')}-{f.get('line') or 0}",
        "rule": rule,
        "severity": f.get("severity", "minor"),
        "claim": f.get("claim") or f.get("message") or "",
        "file": f.get("file", ""),
        "line": f.get("line"),
        "quote": f.get("quote") or "",
        "fix": f.get("fix") or f.get("suggested_fix") or "",
        "tags": tags,
    }


def render(report: dict) -> str:
    shaped = dict(report)
    shaped["findings"] = []
    for n, f in enumerate(report.get("findings", []), start=1):
        rec = to_record(f)
        rec["id"] = f"{n}-{rec['id']}"  # unique even when one rule fires twice on one line
        shaped["findings"].append(rec)
    return kit_render(TEMPLATE.read_text(encoding="utf-8"), ASSETS, shaped)


def family_totals(findings: list, rubric: Path = RUBRIC) -> list:
    """Per mechanical family: how many distinct rules fired, over how many the rubric defines.

    Read from the rubric's own tables (the only place a rule count may be typed by hand), so
    a family at 0/n is shown rather than omitted.
    """
    text = rubric.read_text(encoding="utf-8") if rubric.is_file() else ""
    ids = re.findall(r"^\| `([A-Z]+-[A-Z0-9-]+)` \|", text, re.M)
    fired = {f["rule"] for f in findings}
    out = []
    for fam in MECHANICAL_FAMILIES:
        rules = [i for i in ids if i.split("-", 1)[0] == fam]
        if rules:
            out.append({"family": fam, "fired": len(fired & set(rules)), "total": len(rules)})
    return out


def collect(report_path: Path, calibration: Path | None = None) -> dict:
    """Read nacharbeit_lint.py --format json output into the viewer's shape.

    Keeps every field the linter emits per finding -- line, quote, suggested_fix, angle --
    because a finding without its location and quote is a claim nobody can check.
    """
    raw = json.loads(report_path.read_text(encoding="utf-8"))
    findings = raw if isinstance(raw, list) else raw.get("findings", [])
    out = []
    for f in findings:
        rid = f.get("rule_id", "?")
        out.append({
            "rule": rid,
            "family": rid.split("-", 1)[0],
            "severity": f.get("severity", "minor"),
            # nacharbeit_lint.py emits `fix_tier` and `claim`; the viewer reads
            # `tier` and `message`. Reading the viewer's own names off the
            # linter's output silently defaulted every tier to "sonnet" and left
            # every message blank -- the normaliser existed and still did not
            # normalise. The viewer's names are accepted too, so an already
            # normalised record passes through unchanged.
            "tier": f.get("fix_tier") or f.get("tier") or "sonnet",
            "file": f.get("file", ""),
            "line": f.get("line"),
            "quote": f.get("quote") or "",
            "fix": f.get("suggested_fix") or f.get("fix") or "",
            "angle": f.get("angle") or "",
            "plugin": f.get("plugin") or "",
            "message": f.get("claim") or f.get("message") or "",
        })
    return {
        "findings": out,
        "plugins": len({f["file"].split("/")[1] for f in out if f["file"].count("/") > 1}),
        "families": family_totals(out),
        "calibration": json.loads(calibration.read_text(encoding="utf-8")) if calibration else {},
        "generated": datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%d %H:%M UTC"),
    }


def selftest() -> int:
    fails = []

    def ok(name, cond, extra=""):
        print(f"  {'ok  ' if cond else 'FAIL'} {name}{'' if cond else ': ' + extra}")
        if not cond:
            fails.append(name)

    demo = json.loads(FIXTURE.read_text(encoding="utf-8")) if FIXTURE.is_file() else None
    ok("committed demo fixture exists", demo is not None, str(FIXTURE))
    if demo is None:
        print("\nSELFTEST FAILED")
        return 1
    html = render(demo)
    ok("tokens marker replaced", TOKENS_MARKER not in html and "--bg" in html)
    ok("report-kit marker replaced and kit inlined", KIT_MARKER + "\n</head>" not in html and "const RK = (" in html
       and "--rk-" in html)
    ok("data island carries the findings",
       '<script type="application/json" id="report-data">' in html and "@@DATA@@" not in html)
    ok("the island keeps line, quote and fix",
       all(k in html for k in ('"quote"', '"line"', '"fix"')))
    ok("static h1 matches the title",
       "<title>nacharbeit — review report</title>" in html and "<h1>nacharbeit — review report</h1>" in html)
    ok("CSP is default-src 'none'", "default-src 'none'" in html)
    ok("no network fetches", 'src="http' not in html and 'href="http' not in html)
    ok("a static verdict element exists", 'class="verdict"' in html)
    ok("a static legend exists", 'class="legend ' in html or 'class="legend"' in html)
    ok("the figure-first stage skeleton is present (R9)",
       'id="rk-stage"' in html and "data-rk-figure" in html and 'id="rk-drawer"' in html,
       "a viewer without the stage leads with a table, not its figure")
    ok("no innerHTML assignment", "innerHTML" not in html and "insertAdjacentHTML" not in html)
    sevs = {f["severity"] for f in demo["findings"]}
    tiers = {f["tier"] for f in demo["findings"]}
    ok("the demo shows a blocker", "blocker" in sevs,
       "a review page that never shows its worst severity cannot show what it looks like")
    ok("the demo shows a human-tier finding", "human" in tiers,
       "the tier column exists to separate what a model can close from what it cannot")
    ok("the demo spans more than one rule family", len({f["family"] for f in demo["findings"]}) > 1)
    ok("the calibration block is populated",
       bool(demo.get("calibration", {}).get("planted")))
    # collect() against REAL nacharbeit_lint.py output. It was dead code --
    # reachable from no CLI flag -- which is how it came to read `tier` and
    # `message` when the linter emits `fix_tier` and `claim`.
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        raw = Path(td) / "lint.json"
        raw.write_text(json.dumps({"findings": [{
            "rule_id": "M-FM-DESC", "severity": "major", "fix_tier": "human",
            "file": "plugins/x/skills/a/SKILL.md", "claim": "description does not say when",
            "line": 7, "quote": "description: Helps with things", "angle": "meaning",
            "suggested_fix": "say when to invoke it",
        }]}), encoding="utf-8")
        collected = collect(raw)
        got = collected["findings"][0]
        ok("collect keeps line, quote, fix and angle",
           (got["line"], got["quote"], got["fix"], got["angle"]) ==
           (7, "description: Helps with things", "say when to invoke it", "meaning"), str(got))
        rec = to_record(got)
        ok("the kit record carries the evidence and facets",
           rec["line"] == 7 and rec["quote"] and rec["fix"] and rec["tags"]["tier"] == "human"
           and rec["tags"]["family"] == "M", str(rec))
        fams = {x["family"]: x for x in collected["families"]}
        ok("collect derives family totals from the rubric, not an empty list",
           bool(fams) and fams["M"]["total"] > 0 and all(x["fired"] <= x["total"] for x in fams.values()), str(fams))
        ok("collect maps rule_id -> rule", got["rule"] == "M-FM-DESC", str(got))
        ok("collect derives the family", got["family"] == "M", str(got))
        ok("collect maps fix_tier -> tier, not the default",
           got["tier"] == "human", str(got))
        ok("collect maps claim -> message, not empty",
           got["message"] == "description does not say when", str(got))

    print()
    if fails:
        print(f"SELFTEST FAILED ({len(fails)}): " + ", ".join(fails))
        return 1
    print(f"selftest passed ({len(demo['findings'])} demo findings rendered)")
    return 0


def main(argv: list) -> int:
    parser = argparse.ArgumentParser(
        prog="build_review_html.py",
        description="Render a nacharbeit review: findings by severity, rule family and fix tier.",
        epilog="exit 0 written, 2 could not read an input")
    parser.add_argument("--lint", help="raw nacharbeit_lint.py --format json output, normalised by collect()")
    parser.add_argument("--report", help="a report already in the viewer's shape")
    parser.add_argument("--calibration", help='JSON {"planted", "fired", "blanked"} from test_nacharbeit_lint.py')
    parser.add_argument("--out")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)

    if args.selftest:
        return selftest()
    if args.lint:
        try:
            report = collect(Path(args.lint), Path(args.calibration) if args.calibration else None)
        except FileNotFoundError:
            print(f"no such lint report: {args.lint}", file=sys.stderr)
            return 2
    elif args.report:
        try:
            report = json.loads(Path(args.report).read_text(encoding="utf-8"))
        except FileNotFoundError:
            print(f"no such report: {args.report}", file=sys.stderr)
            return 2
    else:
        parser.error("one of --lint or --report is required unless --selftest is given")

    out = Path(args.out) if args.out else ASSETS / "run-report.html"
    out.write_text(render(report), encoding="utf-8")
    print(f"wrote {out} — {len(report['findings'])} finding(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
