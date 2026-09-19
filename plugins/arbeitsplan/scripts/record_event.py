#!/usr/bin/env python3
"""Persist what an arbeitsplan run did, so the run directory -- not the chat -- is the record.

usage: record_event.py {workflow,phase-output,phase,status,selftest} --run RUNID ...

  workflow      --result FILE   a Workflow tool return (workflows/run.js): appends its
                                span-shaped `events` to run.jsonl, and writes one
                                candidates/<id>.json and referee/<id>.json per candidate
                                it carries, O_CREAT|O_EXCL -- which is what makes
                                land_candidate.py reachable without hand-written files
  phase-output  --phase ID --output FILE
                                a plan-mode phase this session ran itself (CONTRACT,
                                ADJUDICATE): writes phases/<id>.json and records the
                                phase as opened and closed
  phase         --phase ID --status opened|closed [--reason TEXT]
                                an in-session phase boundary; --status halted needs a reason
  status                        what the record says happened, and the single next command

The plan (workflow.json) is never touched here. The Workflow tool has no
filesystem, so a workflow's outcome arrives as a RETURN VALUE that something
outside must persist -- nacharbeit's write_results.py solved the same problem the
same way, and this is that shape for arbeitsplan.

A synthesis that borrowed hunks is a NEW diff nobody refereed. It is written as
candidates/<phaseId>.json, and it only gets a referee record when a later
adjudicator output says `verdict: "land"` -- so land_candidate.py refuses it until
the round was judged, exactly as it refuses an unjudged candidate.

Exit: 0 ok, 1 refused, 2 usage or unreadable input. STDLIB ONLY.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_record  # vendored copy of tools/run-record/run_record.py

PLUGIN = "arbeitsplan"


def _write_once(path: Path, obj: dict) -> bool:
    """O_CREAT|O_EXCL: the create is the lock. An existing record is never overwritten."""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    except FileExistsError:
        return False
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=2)
        fh.write("\n")
    return True


def _span(run_id: str, span: str, node: str, status: str, detail: dict | None = None) -> dict:
    ev: dict = {"trace_id": run_id, "span_id": f"{run_id}.s.{span.replace(' ', '_')}.{node}.{status}",
          "parent_span_id": f"{run_id}.root", "span": span, "node_id": node, "status": status}
    if detail:
        ev["detail"] = detail
    return ev


def cmd_workflow(run: run_record.Run, result: dict) -> list:
    notes = []
    events = result.get("events")
    if not isinstance(events, list):
        raise run_record.RecordError("the result carries no `events` list; is this a run.js return?")
    for ev in events:
        run.append(ev)
    notes.append(f"{len(events)} event(s) appended")

    carry = result.get("carry") or {}
    written = skipped = 0
    for node, payload in carry.items():
        if not isinstance(payload, dict):
            continue
        for cand in payload.get("candidates") or []:
            ok = _write_once(run.dir / "candidates" / f"{cand['candidateId']}.json", {**cand, "phase": node})
            written, skipped = written + ok, skipped + (not ok)
        for v in payload.get("verdicts") or []:
            ok = _write_once(run.dir / "referee" / f"{v['candidateId']}.json", {**v, "phase": node})
            written, skipped = written + ok, skipped + (not ok)
        out = payload.get("output")
        if isinstance(out, dict) and "diff" in out:
            if out.get("borrowed"):
                # A new diff. Recorded as a candidate, and deliberately NOT given a
                # referee record: nothing blind has judged it yet.
                ok = _write_once(run.dir / "candidates" / f"{node}.json", {
                    "candidateId": node, "measured": True, "diff": out["diff"],
                    "filesTouched": out.get("filesTouched") or [], "phase": node,
                    "baseCandidateId": out.get("baseCandidateId"), "borrowed": out["borrowed"]})
                written, skipped = written + ok, skipped + (not ok)
            _write_once(run.dir / "phases" / f"{node}.json", out)
    notes.append(f"{written} candidate/referee record(s) written, {skipped} already existed (never overwritten)")
    if result.get("pending_plan_node"):
        notes.append(f"paused before plan-mode phase {result['pending_plan_node']!r}; resume with "
                     f"startAt {result.get('resumeWith')!r}")
    if result.get("aborted"):
        notes.append(f"HALTED at {result.get('haltedAt')!r}: {result.get('abortReason')}")
    return notes


def cmd_phase_output(run: run_record.Run, phase: str, output: dict) -> list:
    if not _write_once(run.dir / "phases" / f"{phase}.json", output):
        raise run_record.RecordError(f"phases/{phase}.json already exists; a phase output is written once")
    run.append(_span(run.run_id, f"phase {phase}", phase, "opened"))
    refused = bool(output.get("refused"))
    run.append(_span(run.run_id, "invoke_agent", phase, "refuted" if refused else "accepted"))
    for d in output.get("cannotEstablish") or output.get("cannotCheck") or []:
        item = d if isinstance(d, dict) else {"evidence": d}
        detail = {"evidence": item.get("evidence") or item.get("id") or str(d),
                  "resolves_if": item.get("resolves_if") or "a runnable check for this item exists"}
        if item.get("id"):
            detail["criterion"] = item["id"]  # reconcile.py joins on this, never on text
        run.append({**_span(run.run_id, "evaluation", phase, "doubt", detail),
            # sha256, not hash(): str hashing is salted per process, so the id would
            # change between two runs of the same record.
            "span_id": f"{run.run_id}.doubt.{phase}."
                       f"{hashlib.sha256(json.dumps(item, sort_keys=True).encode()).hexdigest()[:12]}"})
    notes = [f"phases/{phase}.json written"]
    # An adjudicator's `land` is the referee record a borrowed synthesis lacked.
    if output.get("verdict") == "land":
        for synth in sorted((run.dir / "candidates").glob("*.json")):
            cand = json.loads(synth.read_text(encoding="utf-8"))
            if cand.get("borrowed") and not (run.dir / "referee" / synth.name).exists():
                _write_once(run.dir / "referee" / synth.name, {
                    "candidateId": cand["candidateId"], "verdict": "accepted", "source": phase,
                    "perCriterion": [{"id": i, "met": True, "evidence": f"adjudicated in {phase}"}
                                     for i in output.get("established") or []]})
                notes.append(f"referee/{synth.name} written from the {phase} verdict")
    run.append(_span(run.run_id, f"phase {phase}", phase, "closed"))
    return notes


def next_command(run_id: str, st: dict) -> str:
    n = st["next"]
    kind = n["kind"]
    if kind == "done":
        return "nothing: the run is finished (complete.json exists)"
    if kind == "inspect-refusal":
        return f"read analysis/arbeitsplan/{run_id}/{n['file']} -- the run was refused, re-compile"
    if kind == "inspect-halt":
        return (f"read the halt at {n['node_id']!r}: {st['halted']['reason']} -- a halt is a "
                "statement about the contract or the environment; re-compile, never re-dispatch")
    if kind == "run-plan-node":
        return (f"run plan-mode phase {n['node_id']!r} in this session, then "
                f"record_event.py phase-output --run {run_id} --phase {n['node_id']} --output <file>")
    if kind == "resume":
        return f"phase {n['node_id']!r} is open: finish it, or record its halt with --status halted"
    return "continue with the next phase in workflow.json"


def selftest() -> int:
    fails: list = []

    def ok(name: str, cond: bool) -> None:
        print(f"  {'ok  ' if cond else 'FAIL'} {name}")
        if not cond:
            fails.append(name)

    rid = "ap-t-9"
    result = {
        "events": [
            {"trace_id": rid, "span_id": f"{rid}.1", "parent_span_id": f"{rid}.wf", "span": "phase build", "node_id": "build", "status": "opened"},
            {"trace_id": rid, "span_id": f"{rid}.2", "parent_span_id": f"{rid}.1", "span": "invoke_agent arbeitsplan:candidate-builder", "node_id": "build:c1", "status": "proposed"},
            {"trace_id": rid, "span_id": f"{rid}.3", "parent_span_id": f"{rid}.wf", "span": "phase build", "node_id": "build", "status": "closed"},
            {"trace_id": rid, "span_id": f"{rid}.4", "parent_span_id": f"{rid}.wf", "span": "plan_node", "node_id": "adjudicate", "status": "pending"},
        ],
        "carry": {
            "build": {"candidates": [{"candidateId": "c1", "measured": True, "diff": "d1"},
                                     {"candidateId": "c2", "measured": True, "diff": "d2"}]},
            "referee": {"verdicts": [{"candidateId": "c1", "verdict": "accepted", "perCriterion": [{"id": "a1", "met": True}]}]},
            "synthesize": {"output": {"baseCandidateId": "c1", "diff": "d3", "borrowed": [{"from": "c2", "beatsOn": "a2"}]}},
        },
        "pending_plan_node": "adjudicate", "resumeWith": None,
    }
    cwd = Path.cwd()
    with tempfile.TemporaryDirectory() as raw:
        try:
            os.chdir(raw)
            run = run_record.open_run(PLUGIN, rid)
            cmd_workflow(run, result)
            d = run.dir
            ok("candidates written one file per id", sorted(p.name for p in (d / "candidates").glob("*.json")) == ["c1.json", "c2.json", "synthesize.json"])
            ok("referee written only for what was judged", sorted(p.name for p in (d / "referee").glob("*.json")) == ["c1.json"])
            ok("a borrowed synthesis gets no referee record", not (d / "referee" / "synthesize.json").exists())
            st = run.status()
            ok("the record reads as a plan-node pause", st["next"] == {"kind": "run-plan-node", "node_id": "adjudicate"})
            (d / "candidates" / "c1.json").write_text('{"candidateId": "c1", "diff": "HAND-EDITED"}')
            cmd_workflow(run, {"events": [], "carry": result["carry"]})
            ok("an existing record is never overwritten", "HAND-EDITED" in (d / "candidates" / "c1.json").read_text())
            cmd_phase_output(run, "adjudicate", {"verdict": "land", "established": ["a1", "a2"],
                                                 "cannotEstablish": [{"id": "a3", "evidence": "e", "resolves_if": "r"}]})
            ok("adjudicator 'land' referees the borrowed synthesis", (d / "referee" / "synthesize.json").is_file())
            st = run.status()
            ok("the plan node is closed after its output", st["pending_plan_node"] is None and "adjudicate" in st["closed_phases"])
            ok("cannotEstablish became a doubt", st["counts"].get("doubt") == 1)
            try:
                cmd_phase_output(run, "adjudicate", {"verdict": "land"})
                ok("a phase output is written once", False)
            except run_record.RecordError:
                ok("a phase output is written once", True)
            try:
                cmd_workflow(run, {"carry": {}})
                ok("a result with no events is refused", False)
            except run_record.RecordError:
                ok("a result with no events is refused", True)
        finally:
            os.chdir(cwd)
    print()
    if fails:
        print(f"SELFTEST FAILED ({len(fails)}): {', '.join(fails)}")
        return 1
    print("record_event selftest passed")
    return 0


def main(argv: list) -> int:
    parser = argparse.ArgumentParser(prog="record_event.py", description=(__doc__ or "").split("\n\n")[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("workflow")
    w.add_argument("--run", required=True)
    w.add_argument("--result", required=True, help="the Workflow return value, as a JSON file")
    po = sub.add_parser("phase-output")
    po.add_argument("--run", required=True)
    po.add_argument("--phase", required=True)
    po.add_argument("--output", required=True)
    ph = sub.add_parser("phase")
    ph.add_argument("--run", required=True)
    ph.add_argument("--phase", required=True)
    ph.add_argument("--status", required=True, choices=["opened", "closed", "halted"])
    ph.add_argument("--reason")
    st = sub.add_parser("status")
    st.add_argument("--run", required=True)
    sub.add_parser("selftest")
    args = parser.parse_args(argv)
    if args.cmd == "selftest":
        return selftest()
    try:
        run = run_record.open_run(PLUGIN, args.run)
        if args.cmd == "status":
            s = run.status()
            print(json.dumps(s, indent=2))
            print(f"\nnext: {next_command(args.run, s)}")
            return 0
        if args.cmd == "phase":
            if args.status == "halted":
                run.halt(args.reason or "", args.phase)
            else:
                run.append(_span(args.run, f"phase {args.phase}", args.phase, args.status))
            print(f"recorded phase {args.phase} {args.status}")
            return 0
        src = args.result if args.cmd == "workflow" else args.output
        try:
            data = json.loads(Path(src).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            print(f"cannot read {src}: {exc}", file=sys.stderr)
            return 2
        notes = cmd_workflow(run, data) if args.cmd == "workflow" else cmd_phase_output(run, args.phase, data)
        for n in notes:
            print(n)
        return 0
    except run_record.RecordError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
