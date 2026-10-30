#!/usr/bin/env python3
"""Render assets/spur-viewer.html from one spur run record (trace.json).

usage: build_spur_html.py [-h] [--trace FILE] [--out FILE] [--selftest]

spur_trace.py run calls render() itself and writes spur-report.html beside the run's
trace.json; this script is the same render as a command, for rebuilding a page from a
kept run record, or the committed demo (`--trace scripts/fixtures/spur-demo.json`) for
a reproducible screenshot.

Why a document and not a timeline: the question a reviewer asks is "which step
produced this file, from what?" -- a chain of links read top to bottom, each step's
inputs and outputs beside its call tree. A flame graph answers "where did the time
go", which is a profiler's question, not provenance's.

Exit: 0 written, 2 could not read the trace.

STDLIB ONLY -- it must run under a bare system python3.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEMPLATE = HERE.parent / "assets" / "spur-viewer.html"
TOKENS = HERE.parent / "assets" / "tokens.css"
FIXTURE = HERE / "fixtures" / "spur-demo.json"

TOKENS_MARKER = "<!--__DESIGN_TOKENS__-->"
DATA_MARKER = "/*__SPUR_DATA__*/"


def render(trace: dict) -> str:
    tpl = TEMPLATE.read_text(encoding="utf-8")
    if TOKENS.is_file():
        tpl = tpl.replace(TOKENS_MARKER, "<style>\n" + TOKENS.read_text(encoding="utf-8") + "\n</style>")
    payload = json.dumps(trace, indent=2)
    # Escape the three characters that could close the <script> element early. The
    # template renders every string through textContent; this is the second barrier.
    payload = payload.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    return tpl.replace(DATA_MARKER, "const SPUR = " + payload + ";")


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
    ok("data marker replaced", DATA_MARKER not in html and "const SPUR" in html)
    ok("no raw '<' survives inside the payload", "</" not in html.split("const SPUR", 1)[1].split("</script>", 1)[0])
    ok("static h1 matches the title",
       "<title>spur — execution trace</title>" in html and "<h1>spur — execution trace</h1>" in html)
    ok("CSP is default-src 'none'", "default-src 'none'" in html)
    ok("no network fetches", 'src="http' not in html and 'href="http' not in html)
    ok("a static verdict element exists", 'class="verdict"' in html)
    ok("a static legend exists", 'class="legend"' in html)
    ok("no innerHTML assignment", "innerHTML" not in html and "insertAdjacentHTML" not in html)
    statuses = {i["status"] for s in demo["steps"] for i in s["inputs"]}
    ok("demo shows a BROKEN link", "broken" in statuses,
       "a demo where the chain holds cannot show what a broken chain looks like (standard C3)")
    ok("demo shows an UNVERIFIED input", "unverified" in statuses,
       "unverified must be visibly distinct from verified, or a reader takes it as a pass")
    ok("demo shows a VERIFIED link and a SOURCE", {"verified", "source"} <= statuses)
    ok("demo shows an in-place rewrite (a path with version 2)",
       any(o["version"] >= 2 for s in demo["steps"] for o in s["outputs"]))
    ok("demo shows an untraced step", any(not s["traced"] for s in demo["steps"]))
    ok("demo carries a call tree", any(t for s in demo["steps"] for t in s["calls"]["threads"]))
    home = str(Path.home())
    ok("demo carries no home path", home not in json.dumps(demo), "redaction failed: " + home)
    ok("demo is real output, labelled as such",
       "spur_trace.py run" in (demo.get("_note") or ""),
       "say which command produced the demo, so it can be regenerated and diffed")

    print()
    if fails:
        print(f"SELFTEST FAILED ({len(fails)}): " + ", ".join(fails))
        return 1
    print(f"selftest passed ({len(demo['steps'])} demo steps rendered)")
    return 0


def main(argv: list) -> int:
    parser = argparse.ArgumentParser(
        prog="build_spur_html.py",
        description="Render spur's execution-trace page from a run record (trace.json).",
        epilog="exit 0 written, 2 could not read the trace",
    )
    parser.add_argument("--trace", help="a spur run record (default: the committed demo)")
    parser.add_argument("--out", help="output HTML (default: spur-report.html beside the trace)")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)

    if args.selftest:
        return selftest()

    src = Path(args.trace) if args.trace else FIXTURE
    try:
        trace = json.loads(src.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"build_spur_html.py: cannot read {src}: {exc}", file=sys.stderr)
        return 2
    out = Path(args.out) if args.out else src.parent / "spur-report.html"
    out.write_text(render(trace), encoding="utf-8")
    print(f"wrote {out} — {len(trace['steps'])} step(s), chain {trace['chain']['verdict']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
