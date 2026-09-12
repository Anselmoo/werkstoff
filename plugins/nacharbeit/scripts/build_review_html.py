#!/usr/bin/env python3
"""Render assets/review-viewer.html from a completed swarm run.

usage: build_review_html.py [-h] [--run RUNID] [--root DIR] [--report FILE] [--out FILE] [--selftest]

A run's own account of itself: which candidates were measured, which were never
fairly tried, what each referee found, where the breaker stood, and which single
diff landed. Reading that out of raw JSON is possible; seeing at a glance that
two candidates were excluded from the denominator is not.

Exit: 0 written, 2 could not read an input.

STDLIB ONLY -- it must run under a bare system python3.
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEMPLATE = HERE.parent / "assets" / "review-viewer.html"
TOKENS = HERE.parent / "assets" / "tokens.css"
FIXTURE = HERE / "fixtures" / "review-demo.json"
TOKENS_MARKER = "<!--__DESIGN_TOKENS__-->"
DATA_MARKER = "/*__REVIEW_DATA__*/"


def render(report: dict) -> str:
    tpl = TEMPLATE.read_text(encoding="utf-8")
    if TOKENS.is_file():
        tpl = tpl.replace(TOKENS_MARKER, "<style>\n" + TOKENS.read_text(encoding="utf-8") + "\n</style>")
    payload = json.dumps(report, indent=2)
    payload = payload.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    return tpl.replace(DATA_MARKER, "const REVIEW = " + payload + ";")


def collect(report_path: Path) -> dict:
    """Read nacharbeit_lint.py --json output into the viewer's shape."""
    raw = json.loads(report_path.read_text(encoding="utf-8"))
    findings = raw if isinstance(raw, list) else raw.get("findings", [])
    out = []
    for f in findings:
        rid = f.get("rule_id", "?")
        out.append({
            "rule": rid,
            "family": rid.split("-", 1)[0],
            "severity": f.get("severity", "minor"),
            "tier": f.get("tier", "sonnet"),
            "file": f.get("file", ""),
            "message": f.get("message", ""),
        })
    return {
        "findings": out,
        "plugins": len({f["file"].split("/")[1] for f in out if f["file"].count("/") > 1}),
        "families": [],
        "calibration": {},
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
    ok("data marker replaced", DATA_MARKER not in html and "const REVIEW" in html)
    ok("static h1 matches the title",
       "<title>nacharbeit — review report</title>" in html and "<h1>nacharbeit — review report</h1>" in html)
    ok("CSP is default-src 'none'", "default-src 'none'" in html)
    ok("no network fetches", 'src="http' not in html and 'href="http' not in html)
    ok("a static verdict element exists", 'class="verdict"' in html)
    ok("a static legend exists", 'class="legend"' in html)
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
    parser.add_argument("--report", help="a prepared report JSON instead of scanning a run")
    parser.add_argument("--out")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)

    if args.selftest:
        return selftest()
    if args.report:
        try:
            report = json.loads(Path(args.report).read_text(encoding="utf-8"))
        except FileNotFoundError:
            print(f"no such report: {args.report}", file=sys.stderr)
            return 2
    else:
        parser.error("--report is required unless --selftest is given")

    out = Path(args.out) if args.out else TEMPLATE.parent / "run-report.html"
    out.write_text(render(report), encoding="utf-8")
    print(f"wrote {out} — {len(report['findings'])} finding(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
