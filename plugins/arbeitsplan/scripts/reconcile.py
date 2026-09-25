#!/usr/bin/env python3
"""Join every declared acceptance id to the evidence the run recorded for it.

usage: reconcile.py --run RUNID [--run-checks] [--candidate CID --tree DIR] | --selftest

The plan says what must hold (workflow.json's acceptance, or the CONTRACT phase's
if one ran). The record says what happened (run.jsonl, referee/, landed.json).
Nothing joined the two, so "every criterion met" was a sentence, not a result.

Per acceptance id, the verdict is one of:

  measured-pass    --run-checks ran its check now: exit 0 (recorded, stdout hashed)
  measured-fail    --run-checks ran its check now: non-zero
  refereed-met     the landed candidate's blind referee recorded it met, with evidence
  refereed-unmet   ...recorded it NOT met
  doubt            the record holds a doubt for it, carrying resolves_if
  UNADDRESSED      none of the above -- nothing in the record speaks to it

`--run-checks` MEASURES rather than transcribes (quo-warranto's rule): the field
that proves a claim is produced here, by running the command and hashing its own
stdout, never copied from the party that made the claim. Each run is appended to
run.jsonl as an `execute_tool` event. A referee that recorded `met` for a
criterion whose check now fails is reported as a CONTRADICTION.

`--run-checks --candidate CID --tree DIR` (#76) is the pre-land measurement: run from
the MAIN repository root, it re-runs every checked criterion of the run's acceptance
with `cwd=DIR` -- a candidate's OWN worktree, not the main tree -- and appends one
`execute_tool` event per check to the MAIN run's run.jsonl, each carrying
`detail.candidate == CID`. It then compares that measurement against the builder's own
report at `candidates/CID.json`, grouped by CRITERION ID ONLY (never by the builder's
own command spelling): any disagreement in EITHER direction (reported 0 / measured
non-zero, or reported non-zero / measured 0) prints `CONTRADICTION <id>: ...` and the
command exits 1. A criterion the builder never reported at all carries no claim, so it
is never a contradiction -- `land_candidate.contradicts()` is the one comparator both
this and `land_candidate.py`'s landing gate call, so they cannot disagree.
`land_candidate.py --apply` reads exactly these events as its landing gate -- an
unmeasured or contradicted candidate is refused.

Exit: 0 every id addressed and nothing contradicted, 1 otherwise, 2 bad input.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import land_candidate  # checks_of(): the ONE normalizer for `check` (#81) --
                        # compile_spec.py imports the same function so this
                        # reader and that validator can never disagree
import run_record  # vendored copy of tools/run-record/run_record.py

PLUGIN = "arbeitsplan"


def _read(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def acceptance(d: Path) -> tuple:
    contract = _read(d / "phases" / "contract.json")
    if contract and isinstance(contract.get("acceptance"), list):
        return contract["acceptance"], "phases/contract.json"
    spec = _read(d / "workflow.json") or {}
    return (spec.get("problem") or {}).get("acceptance") or [], "workflow.json"


def measure(run: run_record.Run, crit: dict, cwd: Path, candidate: str | None = None) -> dict:
    # An acceptance `check` IS a shell program by schema ("a shell command that exits
    # 0 on pass" -- `ruff check x && git diff --exit-code -- y`), so each element
    # runs under /bin/sh, explicitly. Nothing is interpolated into it: the string
    # is the spec's own declared command, run exactly as a CI step would run it.
    #
    # `check` may be a single string or a non-empty list of strings (#81) --
    # land_candidate.checks_of() is the one normalizer every reader traces back
    # to. A criterion passes only when EVERY element exits 0; each element still
    # gets its own execute_tool event, recorded under the SAME criterion id, so
    # an array's elements report under their criterion id exactly as a scalar
    # check's one element always has.
    #
    # `candidate` (#76), when given, runs against THAT candidate's own tree (`cwd`
    # is the candidate worktree, not the main repo) and is carried on every event's
    # `detail.candidate` -- the field land_candidate.py's landing gate reads to tell
    # "this candidate was measured" from "some other candidate was".
    elements = []
    for cmd in land_candidate.checks_of(crit.get("check")):
        p = subprocess.run(["/bin/sh", "-c", cmd], cwd=cwd, capture_output=True, text=True, timeout=600)
        sha = hashlib.sha256(p.stdout.encode()).hexdigest()
        el = {"command": cmd, "exit": p.returncode, "stdoutSha256": sha}
        elements.append(el)
        detail = {"id": crit["id"], **el}
        if candidate is not None:
            detail["candidate"] = candidate
        run.append({"trace_id": run.run_id,
                    "span_id": f"{run.run_id}.check.{crit['id']}.{candidate or ''}.{sha[:12]}.{p.returncode}",
                    "parent_span_id": f"{run.run_id}.root", "span": f"execute_tool {crit['id']}",
                    "node_id": crit["id"], "status": "accepted" if p.returncode == 0 else "refuted",
                    "detail": detail})
    # 0 only when every element exited 0; otherwise the first non-zero exit, so
    # `exit` stays a single real exit code rather than collapsing to a bare flag.
    overall = 0 if elements and all(e["exit"] == 0 for e in elements) else next(
        (e["exit"] for e in elements if e["exit"] != 0), 1)
    return {"id": crit["id"], "command": crit["check"], "exit": overall, "checks": elements}


def measure_candidate(run: run_record.Run, candidate: str, cwd: Path) -> tuple:
    """Measure every checked criterion of the run's acceptance against ONE
    candidate's own tree (`cwd`), and compare each measured element to that
    candidate's own report (`candidates/<candidate>.json`), grouped by criterion
    id only -- never by the builder's own command spelling.

    Returns (rows, contradictions) -- rows carry one entry per checked criterion
    id with its measured element exits; contradictions name a criterion whose
    REPORTED exit(s) disagree with what was just measured, in EITHER direction.
    A criterion the builder never reported at all (`reported == []`) carries no
    claim and is never a contradiction -- `land_candidate.contradicts()` is the
    one comparator this and `land_candidate.py`'s landing gate both call, so the
    two cannot disagree about what counts.
    """
    d = run.dir
    crits, _source = acceptance(d)
    report = _read(d / "candidates" / f"{candidate}.json") or {}
    reported_by_id: dict = {}
    for r in report.get("checks") or []:
        if isinstance(r, dict):
            reported_by_id.setdefault(r.get("id"), []).append(r.get("exit"))
    rows, contradictions = [], []
    for c in crits:
        if not c.get("check"):
            continue
        cid = c["id"]
        m = measure(run, c, cwd, candidate=candidate)
        measured_exits = [e["exit"] for e in m["checks"]]
        reported_exits = reported_by_id.get(cid, [])
        rows.append({"id": cid, "measured": measured_exits, "reported": reported_exits})
        if land_candidate.contradicts(reported_exits, measured_exits):
            contradictions.append(
                f"{cid}: {candidate} reported exit(s) {reported_exits} but measuring "
                f"{candidate}'s own tree now gives {measured_exits}")
    return rows, contradictions


def reconcile(run: run_record.Run, run_checks: bool, cwd: Path) -> tuple:
    d = run.dir
    crits, source = acceptance(d)
    landed = _read(d / "landed.json")
    verdict = _read(d / "referee" / f"{landed['candidate']}.json") if landed else None
    per = {c.get("id"): c for c in (verdict or {}).get("perCriterion") or [] if isinstance(c, dict)}
    # A doubt addresses a criterion by an explicit id -- detail.criterion, or a
    # node_id equal to it -- never by a prefix of its evidence text, where "a1"
    # would silently swallow "a10".
    doubts = {}
    for e in run.events():
        if e["status"] == "doubt":
            key = (e.get("detail") or {}).get("criterion") or e["node_id"]
            doubts.setdefault(key, e)
    rows, contradictions = [], []
    for c in crits:
        cid = c.get("id")
        row = {"id": cid, "criterion": c.get("criterion")}
        if run_checks and c.get("check"):
            m = measure(run, c, cwd)
            row.update(verdict="measured-pass" if m["exit"] == 0 else "measured-fail", evidence=m)
            if m["exit"] != 0 and per.get(cid, {}).get("met"):
                contradictions.append(f"{cid}: the referee recorded met, and its check now exits {m['exit']}")
        elif cid in per:
            row.update(verdict="refereed-met" if per[cid].get("met") else "refereed-unmet",
                       evidence=per[cid].get("evidence"))
        elif cid in doubts:
            row.update(verdict="doubt", evidence=(doubts[cid].get("detail") or {}).get("resolves_if"))
        else:
            row.update(verdict="UNADDRESSED", evidence=None)
        rows.append(row)
    return rows, contradictions, source, landed


def selftest() -> int:
    fails = []

    def ok(name: str, cond: bool) -> None:
        print(f"  {'ok  ' if cond else 'FAIL'} {name}")
        if not cond:
            fails.append(name)

    cwd = Path.cwd()
    with tempfile.TemporaryDirectory() as raw:
        try:
            os.chdir(raw)
            run = run_record.open_run(PLUGIN, "ap-r-1")
            d = run.dir
            (d / "workflow.json").write_text(json.dumps({"problem": {"acceptance": [
                {"id": "a1", "criterion": "passes", "check": "true"},
                {"id": "a2", "criterion": "fails now", "check": "false"},
                {"id": "a3", "criterion": "doubted", "check": None},
                {"id": "a4", "criterion": "forgotten", "check": None},
                {"id": "a5", "criterion": "array, every element passes", "check": ["true", "true"]},
                {"id": "a6", "criterion": "array, one element fails", "check": ["true", "false"]}]}}))
            (d / "referee").mkdir()
            (d / "referee" / "c1.json").write_text(json.dumps({"candidateId": "c1", "verdict": "accepted", "perCriterion": [
                {"id": "a1", "met": True, "evidence": "e1"}, {"id": "a2", "met": True, "evidence": "e2"}]}))
            (d / "landed.json").write_text(json.dumps({"candidate": "c1"}))
            run.append({"trace_id": "ap-r-1", "span_id": "d1", "parent_span_id": "r", "span": "evaluation",
                        "node_id": "adjudicate", "status": "doubt",
                        "detail": {"criterion": "a3", "evidence": "unknown", "resolves_if": "x"}})
            run.append({"trace_id": "ap-r-1", "span_id": "d2", "parent_span_id": "r", "span": "evaluation",
                        "node_id": "adjudicate", "status": "doubt",
                        "detail": {"criterion": "a40", "evidence": "a4 lookalike", "resolves_if": "x"}})

            rows, contra, src, _ = reconcile(run, False, Path(raw))
            v = {r["id"]: r["verdict"] for r in rows}
            ok("reads acceptance from workflow.json when no contract ran", src == "workflow.json")
            ok("referee evidence joins by id", v["a1"] == "refereed-met" and v["a2"] == "refereed-met")
            ok("a doubt addresses its id", v["a3"] == "doubt")
            ok("an id nothing speaks to is UNADDRESSED, even beside a lookalike a40",
               v["a4"] == "UNADDRESSED")

            rows, contra, _, _ = reconcile(run, True, Path(raw))
            v = {r["id"]: r["verdict"] for r in rows}
            ok("--run-checks measures instead of transcribing", v["a1"] == "measured-pass" and v["a2"] == "measured-fail")
            ok("a referee 'met' whose check now fails is a contradiction", any(c.startswith("a2") for c in contra))
            ok("an array check passes only when every element does",
               v["a5"] == "measured-pass" and v["a6"] == "measured-fail")
            ok("every measurement is recorded as execute_tool, one event per ELEMENT "
               "(a1+a2 scalar, a5+a6 two elements each)",
               sum(1 for e in run.events() if e["span"].startswith("execute_tool")) == 6)
            ok("an array's elements report under their criterion id, not a sub-id",
               all(e["node_id"] == "a5" for e in run.events()
                   if e["span"] == "execute_tool a5") and
               sum(1 for e in run.events() if e["span"] == "execute_tool a5") == 2)

            (d / "phases").mkdir()
            (d / "phases" / "contract.json").write_text(json.dumps({"acceptance": [{"id": "b1", "criterion": "c", "check": "true"}]}))
            _, _, src, _ = reconcile(run, False, Path(raw))
            ok("a CONTRACT phase's acceptance replaces the compiled one", src == "phases/contract.json")

            # measure_candidate() (#76): the pre-land, candidate-scoped measurement
            # land_candidate.py's landing gate reads.
            (d / "candidates").mkdir()
            (d / "candidates" / "cX.json").write_text(json.dumps({"measured": True, "diff": "x", "checks": [
                {"id": "b1", "command": "true", "exit": 1}]}))  # dishonest: b1 exits 0
            rows, contra = measure_candidate(run, "cX", Path(raw))
            ok("measure_candidate measures the checked criteria from phases/contract.json",
               {r["id"] for r in rows} == {"b1"})
            ok("a dishonest report is a CONTRADICTION", any(c.startswith("b1") for c in contra))
            ok("measured events for cX carry detail.candidate == cX",
               any((e.get("detail") or {}).get("candidate") == "cX" for e in run.events()
                   if e["span"] == "execute_tool b1"))

            (d / "candidates" / "cY.json").write_text(json.dumps({"measured": True, "diff": "x", "checks": [
                {"id": "b1", "command": "true", "exit": 0}]}))  # honest
            rows, contra = measure_candidate(run, "cY", Path(raw))
            ok("an honest candidate report is not a CONTRADICTION", not contra)

            # (#76 amendment) a different command spelling for the same id is not a
            # contradiction -- reported/measured are compared by criterion id only.
            (d / "candidates" / "cW.json").write_text(json.dumps({"measured": True, "diff": "x", "checks": [
                {"id": "b1", "command": "cd . && true  # the builder's own spelling", "exit": 0}]}))
            rows, contra = measure_candidate(run, "cW", Path(raw))
            ok("a different command spelling for the same id is not a CONTRADICTION", not contra)

            # an unreported criterion (absent from checks[] entirely) is not a
            # contradiction either -- there is nothing to disagree with.
            (d / "candidates" / "cZ.json").write_text(json.dumps({"measured": True, "diff": "x", "checks": []}))
            rows, contra = measure_candidate(run, "cZ", Path(raw))
            ok("an unreported criterion is not a CONTRADICTION", not contra)
            ok("...and is still measured, carrying an empty 'reported'",
               rows and rows[0]["id"] == "b1" and rows[0]["reported"] == [])
        finally:
            os.chdir(cwd)
    print()
    if fails:
        print(f"SELFTEST FAILED ({len(fails)}): {', '.join(fails)}")
        return 1
    print("reconcile selftest passed")
    return 0


def main(argv: list) -> int:
    parser = argparse.ArgumentParser(prog="reconcile.py", description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument("--run")
    parser.add_argument("--run-checks", action="store_true",
                        help="run every acceptance check now, hash its stdout, and record it")
    parser.add_argument("--candidate", help="measure ONE candidate's own tree (#76); "
                                            "requires --run-checks and --tree")
    parser.add_argument("--tree", help="the candidate's own worktree; checks run with this as cwd")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest()
    if not args.run:
        parser.error("--run is required unless --selftest is given")
    if args.candidate and not (args.run_checks and args.tree):
        parser.error("--candidate requires both --run-checks and --tree")
    if args.tree and not args.candidate:
        parser.error("--tree requires --candidate")

    if args.candidate:
        try:
            run = run_record.open_run(PLUGIN, args.run)
        except run_record.RecordError as exc:
            print(f"REFUSED: {exc}", file=sys.stderr)
            return 2
        tree = Path(args.tree).resolve()
        rows, contradictions = measure_candidate(run, args.candidate, tree)
        if not rows:
            print(f"no checked acceptance criteria found for {args.run}", file=sys.stderr)
            return 2
        for r in rows:
            print(f"  {r['id']:<6} measured={r['measured']} reported={r['reported']}")
        for c in contradictions:
            print(f"  CONTRADICTION {c}")
        if contradictions:
            print(f"{len(contradictions)} contradiction(s) for candidate {args.candidate}")
            return 1
        print(f"candidate {args.candidate} measured against its own tree; no contradictions")
        return 0

    try:
        run = run_record.open_run(PLUGIN, args.run)
        rows, contradictions, source, landed = reconcile(run, args.run_checks, Path.cwd())
    except run_record.RecordError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
    if not rows:
        print(f"no acceptance criteria found for {args.run} (looked in {source})", file=sys.stderr)
        return 2
    print(f"reconcile — {args.run}  (acceptance from {source}; landed: "
          f"{landed['candidate'] if landed else 'nothing'})")
    for r in rows:
        print(f"  {r['id']:<6} {r['verdict']:<15} {r['criterion']}")
        if r["evidence"] is not None:
            print(f"         {json.dumps(r['evidence'])[:160]}")
    for c in contradictions:
        print(f"  CONTRADICTION {c}")
    bad = [r for r in rows if r["verdict"] in ("UNADDRESSED", "measured-fail", "refereed-unmet")]
    if bad or contradictions:
        print(f"{len(bad)} criterion(s) not established, {len(contradictions)} contradiction(s)")
        return 1
    print("every criterion is addressed by recorded evidence")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
