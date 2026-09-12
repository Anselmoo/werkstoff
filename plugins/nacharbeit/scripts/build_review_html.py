#!/usr/bin/env python3
"""Render assets/review-viewer.html from a nacharbeit review.

usage: build_review_html.py [-h] [--lint FILE] [--report FILE] [--out FILE] [--selftest]

Findings by rule family, severity and FIX TIER. The tier column is the point: it
separates what a model can close from what is a judgement call, so a reader can
see the size of the remaining work rather than only its count. A family sitting
at 0/n is not evidence of health -- only that nothing exercised it.

  --lint    raw `nacharbeit_lint.py --json` output; normalised here by collect()
  --report  a report already in the viewer's shape

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
            # nacharbeit_lint.py emits `fix_tier` and `claim`; the viewer reads
            # `tier` and `message`. Reading the viewer's own names off the
            # linter's output silently defaulted every tier to "sonnet" and left
            # every message blank -- the normaliser existed and still did not
            # normalise. The viewer's names are accepted too, so an already
            # normalised record passes through unchanged.
            "tier": f.get("fix_tier") or f.get("tier") or "sonnet",
            "file": f.get("file", ""),
            "message": f.get("claim") or f.get("message") or "",
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
    # collect() against REAL nacharbeit_lint.py output. It was dead code --
    # reachable from no CLI flag -- which is how it came to read `tier` and
    # `message` when the linter emits `fix_tier` and `claim`.
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        raw = Path(td) / "lint.json"
        raw.write_text(json.dumps({"findings": [{
            "rule_id": "M-FM-DESC", "severity": "major", "fix_tier": "human",
            "file": "plugins/x/skills/a/SKILL.md", "claim": "description does not say when",
        }]}), encoding="utf-8")
        got = collect(raw)["findings"][0]
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
    parser.add_argument("--lint", help="raw nacharbeit_lint.py --json output, normalised by collect()")
    parser.add_argument("--report", help="a report already in the viewer's shape")
    parser.add_argument("--out")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)

    if args.selftest:
        return selftest()
    if args.lint:
        try:
            report = collect(Path(args.lint))
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

    out = Path(args.out) if args.out else TEMPLATE.parent / "run-report.html"
    out.write_text(render(report), encoding="utf-8")
    print(f"wrote {out} — {len(report['findings'])} finding(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
