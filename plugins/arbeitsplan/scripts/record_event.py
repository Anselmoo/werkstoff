#!/usr/bin/env python3
"""Persist what an arbeitsplan run did, so the run directory -- not the chat -- is the record.

usage: record_event.py {workflow,phase-output,phase,status,finish,selftest} --run RUNID ...

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
  finish                        end the run: complete.json when landed.json exists,
                                FAILED-<stamp>.json when a halt is recorded, refused
                                otherwise -- the marker sweep_artifacts.py waits for

The plan (workflow.json) is never touched here. The Workflow tool has no
filesystem, so a workflow's outcome arrives as a RETURN VALUE that something
outside must persist -- nacharbeit's write_results.py solved the same problem the
same way, and this is that shape for arbeitsplan.

A synthesis that borrowed hunks is a NEW diff nobody refereed. It is written as
candidates/<phaseId>.json, and it only gets a referee record when a later
adjudicator output says `verdict: "land"` -- so land_candidate.py refuses it until
the round was judged, exactly as it refuses an unjudged candidate.

referee/<id>.json (flat, write-once, never overwritten) stays the ONE authoritative
record land_candidate.py reads -- whichever referee phase claims a candidateId first.
But a run can carry MORE THAN ONE referee phase against the SAME candidate ids (a
widened run whose second batch reuses c1/c2), and a flat write-once file would
silently drop every verdict but the first. So EVERY verdict is also written to
referee/<phase>/<id>.json -- write-once per (phase, id), never per id alone -- which
is what scripts/rounds.py reads to rebuild one round per referee phase, in phase
order, across a run and its `supersedes` chain (#78, #93).

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
            # Phase-namespaced twin (#78, #93): independent of whether the flat write
            # above claimed the id first, so a SECOND referee phase reusing this
            # candidateId is still recorded rather than silently skipped. Still
            # write-once -- the same (phase, id) pair is never overwritten either.
            _write_once(run.dir / "referee" / node / f"{v['candidateId']}.json", {**v, "phase": node})
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


def cmd_finish(run: run_record.Run) -> list:
    """End the run in the record, so the run directory says it is over.

    Nothing else in arbeitsplan ever wrote an end marker, so every run -- landed or
    halted -- read as unfinished forever, and sweep_artifacts.py (which removes only
    runs whose record says they ended) could never collect one. Two legal endings,
    both through run_record, never a hand-written file:

      landed.json exists  -> run.finish(): complete.json, refused while a phase is open
      a halt is recorded  -> run.refuse(): FAILED-<stamp>.json carrying the halt reason;
                             a halt means "re-compile", which is what a refused run says
    Anything else is refused: stopping is not an ending, and a marker a run did not
    earn would let the sweep delete a run that is still going.
    """
    st = run.status()
    if st["finished"] or st["failed"]:
        raise run_record.RecordError("the run has already ended; a run ends once")
    landed = None
    try:
        landed = json.loads((run.dir / "landed.json").read_text(encoding="utf-8"))
    except FileNotFoundError:
        pass
    except ValueError as exc:
        raise run_record.RecordError(f"landed.json is unreadable ({exc}); never read as landed") from exc
    if isinstance(landed, dict) and landed.get("candidate"):
        path = run.finish({"landed": landed["candidate"], "paths": len(landed.get("paths") or []),
                           "diverged": "divergedFrom" in landed})
        return [f"finished: {path.name} (landed {landed['candidate']})"]
    if st["halted"]:
        h = st["halted"]
        path = run.refuse(f"halted at {h['node_id']}: {h['reason']}")
        return [f"ended as halted: {path.name} ({h['node_id']}: {h['reason']})"]
    raise run_record.RecordError(
        "nothing ends this run yet: no landed.json and no recorded halt. Land with "
        "land_candidate.py, or record the halt (worktree_pool.py close --halt \"<reason>\"), first")


def next_command(run_id: str, st: dict, landed: bool = False) -> str:
    n = st["next"]
    kind = n["kind"]
    finish = f"record_event.py finish --run {run_id}"
    if kind == "done":
        return "nothing: the run is finished (complete.json exists)"
    if kind == "inspect-refusal":
        return f"read analysis/arbeitsplan/{run_id}/{n['file']} -- the run was refused, re-compile"
    if kind == "inspect-halt":
        return (f"read the halt at {n['node_id']!r}: {st['halted']['reason']} -- a halt is a "
                "statement about the contract or the environment; re-compile, never re-dispatch. "
                f"End this run with {finish}")
    if kind == "continue" and landed:
        return f"the run has landed: {finish}"
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
            ok("the phase-namespaced twin is written alongside the flat file",
               (d / "referee" / "referee" / "c1.json").is_file())
            # A SECOND referee phase reusing candidateId c1: the flat referee/c1.json
            # is claimed already (write-once) and stays untouched, but the
            # phase-namespaced twin under the new phase's own directory is not --
            # this is the #78/#93 fix: a second phase's verdicts are recorded, not
            # silently skipped.
            second = {"events": [{"trace_id": rid, "span_id": f"{rid}.5", "parent_span_id": f"{rid}.wf",
                                  "span": "phase referee2", "node_id": "referee2", "status": "closed"}],
                     "carry": {"referee2": {"verdicts": [{"candidateId": "c1", "verdict": "accepted",
                                                           "perCriterion": [{"id": "a1", "met": True}]}]}}}
            cmd_workflow(run, second)
            ok("flat referee/c1.json is untouched by the second phase (still write-once)",
               json.loads((d / "referee" / "c1.json").read_text()).get("verdict") == "accepted")
            ok("the second phase's verdict is recorded under its own phase-namespaced path",
               (d / "referee" / "referee2" / "c1.json").is_file()
               and json.loads((d / "referee" / "referee2" / "c1.json").read_text()).get("verdict") == "accepted")
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

            # finish: the end marker sweep_artifacts.py waits for, earned or refused.
            def refused(fn) -> bool:
                try:
                    fn()
                except run_record.RecordError:
                    return True
                return False

            landed = run_record.open_run(PLUGIN, "ap-t-10")
            ok("finish refuses a run with no landing and no halt", refused(lambda: cmd_finish(landed)))
            landed.append(_span("ap-t-10", "phase land", "land", "opened"))
            (landed.dir / "landed.json").write_text(json.dumps({"candidate": "c2", "paths": ["src/x.py"]}))
            ok("status does not offer finish while a phase is still open",
               "finish --run" not in next_command("ap-t-10", landed.status(), True))
            ok("finish refuses a landed run while a phase is still open", refused(lambda: cmd_finish(landed)))
            landed.append(_span("ap-t-10", "phase land", "land", "closed"))
            ok("status names finish once the landed run's phases are closed",
               "finish --run ap-t-10" in next_command("ap-t-10", landed.status(), True))
            cmd_finish(landed)
            ok("a landed run finishes as complete.json", (landed.dir / "complete.json").is_file()
               and json.loads((landed.dir / "complete.json").read_text()).get("landed") == "c2")
            ok("a run ends once", refused(lambda: cmd_finish(landed)))

            halted = run_record.open_run(PLUGIN, "ap-t-11")
            halted.append(_span("ap-t-11", "phase build", "build", "opened"))
            halted.halt("CONTRACT PROBLEM: 0/2 usable", "build")
            ok("status names finish for a halted run", "finish --run ap-t-11" in next_command("ap-t-11", halted.status()))
            cmd_finish(halted)
            failed = sorted(halted.dir.glob("FAILED-*.json"))
            ok("a halted run ends as FAILED-<stamp>.json carrying the halt",
               len(failed) == 1 and "CONTRACT PROBLEM" in failed[0].read_text())
            ok("no complete.json for a halted run", not (halted.dir / "complete.json").exists())

            # Imported here, not at module level: the sweep is the consumer this
            # marker exists for, and record_event.py itself never needs it.
            import sweep_artifacts
            eligible, _ = sweep_artifacts.survey(Path(raw))
            names = {p.name for p, _ in eligible}
            ok("the sweep now sees both ended runs", {"ap-t-10", "ap-t-11"} <= names)
            ok("the sweep still keeps the unfinished one", rid not in names)
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
    fin = sub.add_parser("finish")
    fin.add_argument("--run", required=True)
    sub.add_parser("selftest")
    args = parser.parse_args(argv)
    if args.cmd == "selftest":
        return selftest()
    try:
        run = run_record.open_run(PLUGIN, args.run)
        if args.cmd == "status":
            s = run.status()
            print(json.dumps(s, indent=2))
            print(f"\nnext: {next_command(args.run, s, (run.dir / 'landed.json').is_file())}")
            return 0
        if args.cmd == "finish":
            for n in cmd_finish(run):
                print(n)
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
