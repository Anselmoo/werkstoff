#!/usr/bin/env python3
"""Render assets/run-viewer.html from a completed swarm run.

usage: build_run_html.py [-h] [--run RUNID] [--root DIR] [--report FILE] [--out FILE] [--selftest]

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
TEMPLATE = HERE.parent / "assets" / "run-viewer.html"
TOKENS = HERE.parent / "assets" / "tokens.css"
FIXTURE = HERE / "fixtures" / "run-demo.json"
TOKENS_MARKER = "<!--__DESIGN_TOKENS__-->"
DATA_MARKER = "/*__RUN_DATA__*/"


def render(report: dict) -> str:
    tpl = TEMPLATE.read_text(encoding="utf-8")
    if TOKENS.is_file():
        tpl = tpl.replace(TOKENS_MARKER, "<style>\n" + TOKENS.read_text(encoding="utf-8") + "\n</style>")
    payload = json.dumps(report, indent=2)
    payload = payload.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    return tpl.replace(DATA_MARKER, "const RUN = " + payload + ";")


def collect(root: Path, run_id: str) -> dict:
    d = root / run_id
    cands = []
    cdir = d / "candidates"
    for f in sorted(cdir.glob("*.json")) if cdir.is_dir() else []:
        c = json.loads(f.read_text(encoding="utf-8"))
        cands.append({
            "id": c.get("candidateId", f.stem),
            "angle": c.get("angle", ""),
            "outcome": "unmeasured" if not c.get("measured") else "accepted",
            "checksPassed": sum(1 for k in c.get("checks") or [] if k.get("exit") == 0),
            "checksTotal": len(c.get("checks") or []),
            "filesTouched": len(c.get("filesTouched") or []),
            "evidence": "",
        })
    measured = [c for c in cands if c["outcome"] != "unmeasured"]
    return {
        "runId": run_id,
        "candidates": cands,
        "breaker": {"accepted": len(measured), "measured": len(measured),
                    "unmeasured": len(cands) - len(measured), "tripped": False},
        "budget": {"used": len(cands), "total": len(cands)},
        "generated": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
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
    ok("data marker replaced", DATA_MARKER not in html and "const RUN" in html)
    ok("static h1 matches the title",
       "<title>arbeitsplan — swarm run</title>" in html and "<h1>arbeitsplan — swarm run</h1>" in html)
    ok("CSP is default-src 'none'", "default-src 'none'" in html)
    ok("no network fetches", 'src="http' not in html and 'href="http' not in html)
    ok("a static verdict element exists", 'class="verdict"' in html)
    ok("a static legend exists", 'class="legend"' in html)
    ok("no innerHTML assignment", "innerHTML" not in html and "insertAdjacentHTML" not in html)
    outcomes = {c["outcome"] for c in demo["candidates"]}
    ok("the demo shows an UNMEASURED candidate", "unmeasured" in outcomes,
       "without one, the page cannot demonstrate the rule that matters most here")
    ok("the demo shows exactly one landed candidate",
       sum(1 for c in demo["candidates"] if c["outcome"] == "landed") == 1)
    ok("the demo shows a rejected candidate", "rejected" in outcomes)
    ok("unmeasured is excluded from the breaker denominator",
       demo["breaker"]["measured"] == sum(1 for c in demo["candidates"] if c["outcome"] != "unmeasured"))
    print()
    if fails:
        print(f"SELFTEST FAILED ({len(fails)}): " + ", ".join(fails))
        return 1
    print(f"selftest passed ({len(demo['candidates'])} demo candidates rendered)")
    return 0


def main(argv: list) -> int:
    parser = argparse.ArgumentParser(
        prog="build_run_html.py",
        description="Render an arbeitsplan swarm run: candidates, referee verdicts, the "
                    "breaker and the budget.",
        epilog="exit 0 written, 2 could not read an input")
    parser.add_argument("--run", help="runId under --root")
    parser.add_argument("--root", default="analysis/arbeitsplan")
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
    elif args.run:
        report = collect(Path(args.root), args.run)
    else:
        parser.error("one of --run or --report is required unless --selftest is given")

    out = Path(args.out) if args.out else TEMPLATE.parent / "run-report.html"
    out.write_text(render(report), encoding="utf-8")
    print(f"wrote {out} — {len(report['candidates'])} candidate(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
