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


def _read_json(path: Path):
    """Parse one JSON file, or None if it is absent or unreadable.

    Unreadable is NOT the same as empty: the caller reports what it could not
    read rather than rendering a confident page over a missing input.
    """
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def collect(root: Path, run_id: str) -> dict:
    """Derive the report from the run's OWN records, never from assumption.

    This used to label every measured candidate `accepted`, set the breaker's
    numerator to the measured count and both budget numbers to the candidate
    count -- so the page said the breaker held and the budget was exactly spent
    no matter what actually happened. A report that cannot be wrong cannot be
    evidence. Every field below now comes from a file on disk, and where the
    file is missing the report SAYS so instead of filling the gap.
    """
    d = root / run_id
    cands = []

    # candidateId -> referee record, written one per judged candidate.
    verdicts = {}
    rdir = d / "referee"
    for f in sorted(rdir.glob("*.json")) if rdir.is_dir() else []:
        rec = _read_json(f)
        if isinstance(rec, dict) and rec.get("candidateId"):
            verdicts[rec["candidateId"]] = rec

    landed_rec = _read_json(d / "landed.json")
    landed_id = landed_rec.get("candidateId") if isinstance(landed_rec, dict) else None

    cdir = d / "candidates"
    for f in sorted(cdir.glob("*.json")) if cdir.is_dir() else []:
        c = _read_json(f)
        if not isinstance(c, dict):
            continue
        cid = c.get("candidateId", f.stem)
        v = verdicts.get(cid)
        if not c.get("measured"):
            outcome, evidence = "unmeasured", ""
        elif cid == landed_id:
            outcome, evidence = "landed", (v or {}).get("note", "") or ""
        elif v is None:
            # NOT `accepted`. No referee record means nothing judged this
            # candidate, which is a different statement from judging it good.
            outcome, evidence = "unrefereed", "no referee record for this candidate"
        elif v.get("verdict") == "accepted":
            met = [x for x in (v.get("perCriterion") or []) if x.get("met")]
            outcome = "accepted"
            evidence = f"{len(met)}/{len(v.get('perCriterion') or [])} criteria met"
        else:
            outcome = "rejected"
            evidence = v.get("verdict", "") + (": " + v["note"] if v.get("note") else "")
        cands.append({
            "id": cid,
            "angle": c.get("angle", ""),
            "outcome": outcome,
            "checksPassed": sum(1 for k in c.get("checks") or [] if k.get("exit") == 0),
            "checksTotal": len(c.get("checks") or []),
            "filesTouched": len(c.get("filesTouched") or []),
            "evidence": evidence,
        })

    measured = [c for c in cands if c["outcome"] != "unmeasured"]
    accepted = [c for c in measured if c["outcome"] in ("accepted", "landed")]
    # The same 2/3 rule the workflow enforces, computed over the same classes:
    # the unmeasured are excluded from the denominator, never counted as
    # rejections.
    tripped = bool(measured) and len(accepted) * 3 < len(measured) * 2

    # Budget comes from the compiled spec and the dispatch ledger the hook
    # writes -- the two authorities that actually decide it. Absent either, the
    # page reports that it does not know rather than printing a reassuring 0/0.
    spec = _read_json(d / "workflow.json")
    total = None
    if isinstance(spec, dict) and isinstance(spec.get("budget"), dict):
        t = spec["budget"].get("totalDispatches")
        total = t if isinstance(t, int) else None
    ddir = d / "dispatch"
    used = len(list(ddir.glob("*.json"))) if ddir.is_dir() else None

    return {
        "runId": run_id,
        "candidates": cands,
        "breaker": {"accepted": len(accepted), "measured": len(measured),
                    "unmeasured": len(cands) - len(measured), "tripped": tripped},
        "budget": {"used": used, "total": total},
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
    # collect() against a REAL run directory. The old selftest rendered a
    # hand-written fixture and never called collect at all, which is precisely
    # why collect could label every measured candidate `accepted` and fabricate
    # the breaker and budget without a single test going red.
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        run = root / "r1"
        (run / "candidates").mkdir(parents=True)
        (run / "referee").mkdir(parents=True)
        (run / "dispatch").mkdir(parents=True)

        def w(rel, obj):
            (run / rel).write_text(json.dumps(obj), encoding="utf-8")

        w("workflow.json", {"budget": {"totalDispatches": 9}})
        w("candidates/c1.json", {"candidateId": "c1", "measured": True, "checks": [{"exit": 0}]})
        w("candidates/c2.json", {"candidateId": "c2", "measured": True})
        w("candidates/c3.json", {"candidateId": "c3", "measured": False})
        w("candidates/c4.json", {"candidateId": "c4", "measured": True})
        w("referee/c1.json", {"candidateId": "c1", "verdict": "accepted",
                              "perCriterion": [{"id": "a", "met": True}]})
        w("referee/c2.json", {"candidateId": "c2", "verdict": "rejected", "note": "criterion a"})
        w("landed.json", {"candidateId": "c1"})
        (run / "dispatch" / "x.json").write_text("{}", encoding="utf-8")

        got = collect(root, "r1")
        by = {c["id"]: c["outcome"] for c in got["candidates"]}
        ok("a landed candidate reads `landed`", by.get("c1") == "landed", str(by))
        ok("a rejected verdict reads `rejected`, not accepted", by.get("c2") == "rejected", str(by))
        ok("an unmeasured candidate stays `unmeasured`", by.get("c3") == "unmeasured", str(by))
        # The finding that started this: no referee record must NOT read as accepted.
        ok("no referee record reads `unrefereed`, never `accepted`",
           by.get("c4") == "unrefereed", str(by))
        ok("breaker numerator counts only accepted/landed",
           got["breaker"]["accepted"] == 1, str(got["breaker"]))
        ok("breaker denominator excludes the unmeasured",
           got["breaker"]["measured"] == 3, str(got["breaker"]))
        ok("breaker trips below two thirds", got["breaker"]["tripped"] is True, str(got["breaker"]))
        ok("budget total comes from workflow.json", got["budget"]["total"] == 9, str(got["budget"]))
        ok("budget used comes from the dispatch ledger", got["budget"]["used"] == 1, str(got["budget"]))

        # A run with neither spec nor ledger must report that it does not know.
        bare = root / "r2"
        (bare / "candidates").mkdir(parents=True)
        got2 = collect(root, "r2")
        ok("an unknown budget is null, not a reassuring 0/0",
           got2["budget"] == {"used": None, "total": None}, str(got2["budget"]))

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
