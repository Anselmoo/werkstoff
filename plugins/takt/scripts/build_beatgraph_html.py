#!/usr/bin/env python3
"""Render assets/beatgraph-viewer.html from the repository's declared beats.

usage: build_beatgraph_html.py [-h] [--repo PATH] [--report FILE] [--out FILE] [--selftest]

takt enforces an order it never authors. This renders that order so a reader can
see it: every declared beat, whether its marker exists yet, and which plugin
produces it. Without this, the only way to know what takt is currently blocking
is to trip over a denial.

Reads each plugin's `.claude-plugin/beats.json` and the markers on disk, or a
prepared report (`--report`) for a reproducible screenshot.

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
TEMPLATE = HERE.parent / "assets" / "beatgraph-viewer.html"
TOKENS = HERE.parent / "assets" / "tokens.css"
FIXTURE = HERE / "fixtures" / "beatgraph-demo.json"

TOKENS_MARKER = "<!--__DESIGN_TOKENS__-->"
DATA_MARKER = "/*__BEATGRAPH_DATA__*/"


def collect(repo: Path) -> dict:
    """Build the report from declarations plus the markers actually on disk."""
    plugins = repo / "plugins"
    decls = {}
    for d in sorted(plugins.iterdir()) if plugins.is_dir() else []:
        f = d / ".claude-plugin" / "beats.json"
        if f.is_file():
            try:
                decls[d.name] = json.loads(f.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, ValueError) as exc:
                raise SystemExit(f"build_beatgraph_html.py: {f}: {exc}")

    produced = {}
    produces = []
    for name, d in decls.items():
        for pr in d.get("produces") or []:
            if pr.get("marker"):
                produced[pr["marker"]] = name
                produces.append({"marker": pr["marker"], "plugin": name,
                                 "after": pr.get("after", "?"), "meaning": pr.get("meaning", "")})

    beats = []
    for name, d in sorted(decls.items()):
        for req in d.get("requires") or []:
            marker, before = req.get("marker"), req.get("before")
            if not marker or not before:
                continue
            # Repo-level by construction: a declared requirement is a durable
            # fact about the repository, not a fact about one run.
            path = repo / ".takt" / marker
            beats.append({
                "gates": before,
                "marker": f".takt/{marker}",
                "producedBy": produced.get(marker),
                "scope": "repo-level",
                "satisfied": path.exists(),
                "reason": req.get("reason", ""),
                "optional": bool(req.get("optional")),
            })

    return {
        "beats": beats,
        "produces": sorted(produces, key=lambda p: p["marker"]),
        "declarations": len(decls),
        "generated": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    }


def render(report: dict) -> str:
    tpl = TEMPLATE.read_text(encoding="utf-8")
    if TOKENS.is_file():
        tpl = tpl.replace(TOKENS_MARKER, "<style>\n" + TOKENS.read_text(encoding="utf-8") + "\n</style>")
    payload = json.dumps(report, indent=2)
    # Escape the three characters that could close the <script> element early.
    payload = payload.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    return tpl.replace(DATA_MARKER, "const BEATGRAPH = " + payload + ";")


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
    ok("data marker replaced", DATA_MARKER not in html and "const BEATGRAPH" in html)
    ok("no raw '<' survives inside the payload",
       "\\u003c" in html or "<" not in json.dumps(demo))
    ok("static h1 matches the title",
       "<title>takt — beat graph</title>" in html and "<h1>takt — beat graph</h1>" in html)
    ok("CSP is default-src 'none'", "default-src 'none'" in html)
    ok("no network fetches", "src=\"http" not in html and "href=\"http" not in html)
    ok("a static verdict element exists", 'class="verdict"' in html)
    ok("a static legend exists", 'class="legend"' in html)
    ok("no innerHTML assignment", "innerHTML" not in html and "insertAdjacentHTML" not in html)
    ok("blocked beats appear in the demo",
       any(not b["satisfied"] for b in demo["beats"]),
       "a demo where nothing is blocked cannot show what blocking looks like")
    ok("satisfied beats appear too",
       any(b["satisfied"] for b in demo["beats"]),
       "a demo where everything is blocked cannot show the other state")

    print()
    if fails:
        print(f"SELFTEST FAILED ({len(fails)}): " + ", ".join(fails))
        return 1
    print(f"selftest passed ({len(demo['beats'])} demo beats rendered)")
    return 0


def main(argv: list) -> int:
    parser = argparse.ArgumentParser(
        prog="build_beatgraph_html.py",
        description="Render takt's beat graph: every declared cross-plugin ordering rule "
                    "and whether its marker exists yet.",
        epilog="exit 0 written, 2 could not read an input",
    )
    parser.add_argument("--repo", default=".", help="repository root (default: .)")
    parser.add_argument("--report", help="a prepared report JSON instead of scanning the repo")
    parser.add_argument("--out", help="output HTML (default: alongside the template)")
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
        report = collect(Path(args.repo))

    out = Path(args.out) if args.out else TEMPLATE.parent / "beatgraph-report.html"
    out.write_text(render(report), encoding="utf-8")
    blocked = sum(1 for b in report["beats"] if not b["satisfied"])
    print(f"wrote {out} — {len(report['beats'])} beat(s), {blocked} blocked")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
