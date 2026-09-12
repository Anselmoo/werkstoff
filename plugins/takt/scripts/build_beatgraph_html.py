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


def _compiler(repo: Path):
    """arbeitsplan's repo_beats, imported rather than reimplemented.

    The viewer and the compiler must not be two opinions about which beats
    exist. When they drifted once before -- validate_beats.py rejecting output
    takt's own guard handled correctly -- the lesson recorded was that a second
    implementation of the same rule is believed right up until it is wrong.
    Returns None when arbeitsplan is not installed; the viewer then renders
    declarations only and says so.
    """
    mod = repo / "plugins" / "arbeitsplan" / "scripts" / "emit_beats.py"
    if not mod.is_file():
        return None
    import importlib.util
    spec = importlib.util.spec_from_file_location("arbeitsplan_emit_beats", mod)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def collect(repo: Path) -> dict:
    """Build the report from the declarations, the COMPILER's verdict, and the
    evidence actually on disk."""
    plugins = repo / "plugins"
    decls = {}
    for d in sorted(plugins.iterdir()) if plugins.is_dir() else []:
        f = d / ".claude-plugin" / "beats.json"
        if f.is_file():
            try:
                decls[d.name] = json.loads(f.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, ValueError) as exc:
                raise SystemExit(f"build_beatgraph_html.py: {f}: {exc}")

    produces = []
    for name, d in decls.items():
        for pr in d.get("produces") or []:
            ev = pr.get("evidence") or {}
            produces.append({
                "marker": pr.get("marker", "?"), "plugin": name,
                "after": pr.get("after", "?"), "meaning": pr.get("meaning", ""),
                "evidenceKind": ev.get("kind", "undeclared"),
                "evidencePath": ev.get("path", ""),
                "why": ev.get("why", ""),
            })

    m = _compiler(repo)
    beats, refused = [], []
    if m is not None:
        compiled, dropped, refusals, _malformed = m.repo_beats(decls, plugins)
        for b in compiled:
            path = repo / b["require"]
            kind = b.get("requireKind", "any")
            sat = path.is_file() if kind == "file" else (
                path.is_dir() if kind == "dir" else path.exists())
            beats.append({
                "gates": b["skills"][0] if b["skills"] else "?",
                "marker": b["require"], "producedBy": None,
                "scope": kind, "satisfied": sat, "reason": b.get("reason", ""),
            })
        refused = [{"gates": w, "marker": mk, "reason": r, "why": why}
                   for w, mk, r, why in refusals]

    return {
        "beats": beats,
        "refused": refused,
        "produces": sorted(produces, key=lambda p: p["marker"]),
        "declarations": len(decls),
        "compilerAvailable": m is not None,
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
    # The check that matters: the viewer's beat list is the COMPILER's beat
    # list. If these ever disagree the page is lying about what is enforced.
    live = collect(Path(__file__).resolve().parent.parent.parent)
    m = _compiler(Path(__file__).resolve().parent.parent.parent)
    if m is not None:
        decls = {d.parent.parent.name: json.loads(d.read_text())
                 for d in sorted((Path(__file__).resolve().parent.parent.parent / "plugins")
                                 .glob("*/.claude-plugin/beats.json"))}
        compiled, _, _, _ = m.repo_beats(decls, Path(__file__).resolve().parent.parent.parent / "plugins")
        ok("viewer beat count equals the compiler's", len(live["beats"]) == len(compiled),
           f"viewer {len(live['beats'])} vs compiler {len(compiled)}")
        ok("a refusal is carried through to the page, not dropped",
           len(live["refused"]) >= 1,
           "a requirement the compiler refused must be visible, or the page implies it was never declared")
    ok("demo shows a BLOCKED beat",
       any(not b["satisfied"] for b in demo["beats"]),
       "a demo where nothing is blocked cannot show what blocking looks like")
    ok("demo shows a SATISFIED beat",
       any(b["satisfied"] for b in demo["beats"]),
       "a demo where everything is blocked cannot show the other state")
    ok("demo shows a REFUSED requirement",
       len(demo.get("refused") or []) >= 1,
       "a refusal is a result, not an omission -- a page that never shows one implies every "
       "declared requirement became a beat")
    ok("demo shows an evidence kind of 'none'",
       any(p.get("evidenceKind") == "none" for p in demo["produces"]),
       "the undependable case is the one a reader most needs to see named")
    ok("demo is labelled synthetic",
       "SYNTHETIC" in (demo.get("_note") or ""),
       "demo data that reads as live state misleads about what this repo currently enforces")

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
