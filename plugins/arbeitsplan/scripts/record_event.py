#!/usr/bin/env python3
"""Persist what an arbeitsplan run did, so the run directory -- not the chat -- is the record.

usage: record_event.py {workflow,candidate,referee,phase-output,phase,status,finish,selftest} --run RUNID ...

  workflow      --result FILE   a Workflow tool return (workflows/run.js): appends its
                                span-shaped `events` to run.jsonl, and writes one
                                candidates/<id>.json and referee/<id>.json per candidate
                                it carries, O_CREAT|O_EXCL -- which is what makes
                                land_candidate.py reachable without hand-written files
  candidate     --phase ID --result FILE [--tree DIR]
                                an IN-SESSION builder batch (one result or a list):
                                writes candidates/<id>.json (write-once), the file
                                land_candidate.py and reconcile.py read; refused unless
                                the phase is opened and every result has the
                                candidate-builder shape. --tree (one result only) takes
                                diff and filesTouched from the worktree itself and notes
                                whether the builder's self-report differed
  referee       --phase ID --verdict FILE
                                an IN-SESSION referee batch (one verdict or a list):
                                writes referee/<id>.json (write-once) and the
                                referee/<phase>/<id>.json twin rounds.py reads, exactly as
                                `workflow` does for a returned batch; refused unless the
                                phase is opened and every verdict is well-formed
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
import subprocess
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


def _event_problem(run: run_record.Run, ev: object) -> str | None:
    """Why run.append() would refuse `ev`, decided BEFORE anything is appended.

    Built on run_record's own REQUIRED, STATUSES and MAX_LINE, and on the exact
    serialization its _write_line uses (compact, sorted keys, plus `kind` and an
    `at` of the length _now() produces) -- a copy of those rules would drift. It
    exists so a result is refused whole: appending event by event, a refusal at the
    Nth event left N-1 appended and every candidate/referee file unwritten (#76's
    record, half-persisted). The size limit is the one a real run hit: a referee
    event carrying 34 criteria of evidence was 4120 bytes.
    """
    if not isinstance(ev, dict):
        return "an event is not an object"
    missing = [k for k in run_record.REQUIRED if not ev.get(k)]
    if missing:
        return f"an event lacks {missing}"
    if ev["status"] not in run_record.STATUSES:
        return f"{ev['span_id']}: status {ev['status']!r} is not in the closed set"
    if ev["trace_id"] != run.run_id:
        return f"{ev['span_id']}: trace_id {ev['trace_id']!r} is not this run"
    if ev["status"] == "doubt" and not (ev.get("detail") or {}).get("resolves_if"):
        return f"{ev['span_id']}: a doubt without detail.resolves_if"
    line = json.dumps({"kind": "event", "at": ev.get("at") or "0000-00-00T00:00:00+00:00", **ev},
                      separators=(",", ":"), sort_keys=True) + "\n"
    if len(line.encode()) > run_record.MAX_LINE:
        return (f"{ev['span_id']} ({ev['span']}) is {len(line.encode())} bytes, over the "
                f"{run_record.MAX_LINE}-byte atomic line; its detail must be a summary, not a payload")
    return None


def cmd_workflow(run: run_record.Run, result: dict) -> list:
    notes = []
    events = result.get("events")
    if not isinstance(events, list):
        raise run_record.RecordError("the result carries no `events` list; is this a run.js return?")
    problems = [p for p in (_event_problem(run, ev) for ev in events) if p]
    if problems:
        raise run_record.RecordError("nothing recorded -- " + "; ".join(problems[:5])
                                     + (f"; and {len(problems) - 5} more" if len(problems) > 5 else ""))
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


VERDICTS = {"accepted", "accepted_different_approach", "rejected", "cannot_judge"}


def cmd_referee(run: run_record.Run, phase: str, data: object) -> list:
    """Record one IN-SESSION referee batch exactly as `workflow` records a returned one.

    rounds.py rebuilds one round per referee phase from referee/<phase>/<id>.json,
    and only `workflow --result` (the workflow backend) ever wrote that twin. An
    in-session run's verdicts therefore produced no rounds at all, and the #78
    SYNTHESIZE and #93 moving-residual rules could never fire on that backend
    (run ap-2026-09-25-6f6f: three referee phases, `rounds.py record` -> []).

    `data` is one verdict object or a list of them, in the referee's own shape
    ({candidateId, verdict, perCriterion[, note, rationaleLeaked]}). The whole batch
    is validated before anything is written, and it is refused rather than guessed
    at: the phase must already be opened in run.jsonl (rounds.py orders rounds by
    that event), every verdict must name its candidate, use the referee vocabulary
    and carry perCriterion, and a (phase, candidateId) already recorded is never
    overwritten. The flat referee/<id>.json stays write-once and first-come -- the
    record land_candidate.py reads -- so a later phase reusing an id adds only its
    twin, which is the point.
    """
    verdicts: list = data if isinstance(data, list) else [data]
    if not verdicts:
        raise run_record.RecordError("the verdict file holds no verdicts")
    st = run.status()
    if st["finished"] or st["failed"]:
        raise run_record.RecordError("the run has ended; a verdict recorded afterwards was never part of it")
    opened = {e["node_id"] for e in run.events()
              if str(e.get("span", "")).startswith("phase ") and e.get("status") == "opened"}
    if phase not in opened:
        raise run_record.RecordError(
            f"phase {phase!r} was never opened in run.jsonl; record it first with "
            f"record_event.py phase --run {run.run_id} --phase {phase} --status opened "
            "-- rounds.py orders rounds by that event")
    problems, seen = [], set()
    for i, v in enumerate(verdicts):
        where = f"verdict[{i}]"
        if not isinstance(v, dict):
            problems.append(f"{where} is not an object")
            continue
        cid = v.get("candidateId")
        if not isinstance(cid, str) or not cid:
            problems.append(f"{where} names no candidateId")
            continue
        if cid in seen:
            problems.append(f"{where} repeats candidateId {cid!r} within one batch")
        seen.add(cid)
        if v.get("verdict") not in VERDICTS:
            problems.append(f"{cid}: verdict {v.get('verdict')!r} is not one of {sorted(VERDICTS)}")
        per = v.get("perCriterion")
        if not isinstance(per, list) or not all(isinstance(p, dict) and p.get("id") and isinstance(p.get("met"), bool)
                                                 for p in per):
            problems.append(f"{cid}: perCriterion must be a list of {{id, met: bool, evidence}}")
        if (run.dir / "referee" / phase / f"{cid}.json").exists():
            problems.append(f"{cid}: already recorded for phase {phase!r}; a verdict is written once")
    if problems:
        raise run_record.RecordError("nothing written -- " + "; ".join(problems))
    # Every event is built -- and sized -- before any file is written. The event
    # carries a SUMMARY and the path of the full record: a verdict's perCriterion
    # with evidence outgrew run_record's 4096-byte atomic line on a real 34-criterion
    # run, and failing after the files were written would leave half a batch.
    events = []
    for v in verdicts:
        cid = v["candidateId"]
        status = {"accepted": "accepted", "cannot_judge": "doubt"}.get(v["verdict"], "refuted")
        detail = {"verdict": v["verdict"], "record": f"referee/{phase}/{cid}.json",
                  "unmet": [p["id"] for p in v["perCriterion"] if p["met"] is False]}
        if status == "doubt":
            detail["resolves_if"] = "a criterion with a runnable check that decides this diff"
        ev = _span(run.run_id, "invoke_agent arbeitsplan:candidate-referee", f"{phase}:{cid}", status, detail)
        problem = _event_problem(run, ev)
        if problem:
            raise run_record.RecordError(f"nothing written -- {problem}")
        events.append(ev)
    notes = []
    for v, ev in zip(verdicts, events, strict=True):
        cid = v["candidateId"]
        rec = {**v, "phase": phase}
        flat = _write_once(run.dir / "referee" / f"{cid}.json", rec)
        _write_once(run.dir / "referee" / phase / f"{cid}.json", rec)
        run.append(ev)
        notes.append(f"referee/{phase}/{cid}.json written ({v['verdict']})"
                     + ("" if flat else f"; flat referee/{cid}.json kept from an earlier phase"))
    return notes


CANDIDATE_LISTS = ("filesTouched", "checks", "outOfScopeWrites")


def _tree_diff(tree: Path) -> tuple[str, list]:
    """(diff, paths) of a candidate worktree as it actually stands, untracked files included.

    `git add -N` records only the intent to add, so a created file shows up in
    `git diff` as a new-file hunk -- which is what land_candidate.py's `git apply`
    needs -- without staging any content.
    """
    def git(*argv: str) -> str:
        done = subprocess.run(["git", "-C", str(tree), *argv], capture_output=True, text=True)
        if done.returncode != 0:
            raise run_record.RecordError(f"git {' '.join(argv)} failed in {tree}: {done.stderr.strip()}")
        return done.stdout

    if not tree.is_dir():
        raise run_record.RecordError(f"--tree {tree} is not a directory")
    git("add", "-N", ".")
    return git("diff"), git("diff", "--name-only").split()


def cmd_candidate(run: run_record.Run, phase: str, data: object, tree: Path | None = None) -> list:
    """Record one IN-SESSION builder batch, as `workflow` records a returned one.

    land_candidate.py refuses without candidates/<id>.json and reconcile.py
    compares a candidate's reported checks[] against it, but only `workflow
    --result` (the workflow backend) ever wrote that file. An in-session run
    dispatches arbeitsplan:candidate-builder itself, so its session wrote the
    file by hand, through Bash, which the guard's matcher never sees.

    `data` is one builder result or a list of them, in candidate-builder.md's
    shape. The batch is validated whole before anything is written, and refused
    rather than guessed at: the phase must be opened, the shape must hold, and a
    candidate already recorded is never overwritten.

    `--tree` replaces the self-reported `diff` and `filesTouched` with what the
    worktree actually holds. Builders paraphrase long diffs -- in run
    ap-2026-09-26-0086 both elided the lock-file hunks as "[...]", a diff that
    would not apply -- so the record notes whether the report differed. It takes
    exactly one result: which worktree belongs to which candidate of a list is
    not something to infer.
    """
    results: list = data if isinstance(data, list) else [data]
    if not results:
        raise run_record.RecordError("the result file holds no builder results")
    if tree is not None and len(results) != 1:
        raise run_record.RecordError(f"--tree names one worktree but the file holds {len(results)} results; "
                                     "record each candidate with its own --tree")
    st = run.status()
    if st["finished"] or st["failed"]:
        raise run_record.RecordError("the run has ended; a candidate recorded afterwards was never part of it")
    opened = {e["node_id"] for e in run.events()
              if str(e.get("span", "")).startswith("phase ") and e.get("status") == "opened"}
    if phase not in opened:
        raise run_record.RecordError(
            f"phase {phase!r} was never opened in run.jsonl; record it first with "
            f"record_event.py phase --run {run.run_id} --phase {phase} --status opened")
    problems, seen = [], set()
    for i, r in enumerate(results):
        where = f"result[{i}]"
        if not isinstance(r, dict):
            problems.append(f"{where} is not an object")
            continue
        cid = r.get("candidateId")
        if not isinstance(cid, str) or not cid:
            problems.append(f"{where} names no candidateId")
            continue
        if cid in seen:
            problems.append(f"{where} repeats candidateId {cid!r} within one batch")
        seen.add(cid)
        if not isinstance(r.get("angle"), str) or not r["angle"]:
            problems.append(f"{cid}: angle must be a non-empty string")
        if not isinstance(r.get("measured"), bool):
            problems.append(f"{cid}: measured must be true or false, never absent")
        elif r["measured"] and tree is None and not (isinstance(r.get("diff"), str) and r["diff"].strip()):
            problems.append(f"{cid}: a measured candidate carries no diff")
        for key in CANDIDATE_LISTS:
            if not isinstance(r.get(key), list):
                problems.append(f"{cid}: {key} must be a list")
        checks = r.get("checks")
        if isinstance(checks, list) and not all(
                isinstance(c, dict) and c.get("id") and isinstance(c.get("command"), str)
                and isinstance(c.get("exit"), int) and not isinstance(c.get("exit"), bool) for c in checks):
            problems.append(f"{cid}: checks must be a list of {{id, command, exit: int}}")
        if (run.dir / "candidates" / f"{cid}.json").exists():
            problems.append(f"{cid}: candidates/{cid}.json already exists; a candidate is written once")
    if problems:
        raise run_record.RecordError("nothing written -- " + "; ".join(problems))
    records, events = [], []
    for r in results:
        cid = r["candidateId"]
        rec = {**r, "phase": phase}
        detail: dict = {"record": f"candidates/{cid}.json"}
        if tree is not None and r["measured"]:
            diff, paths = _tree_diff(tree)
            if not diff.strip():
                raise run_record.RecordError(f"nothing written -- {cid} reports measured, but {tree} holds no diff")
            rec.update(diff=diff, filesTouched=paths, diffSource="tree",
                       selfReportDiffered=(r.get("diff") or "") != diff,
                       selfReportedDiffSha256=hashlib.sha256((r.get("diff") or "").encode()).hexdigest())
            detail["selfReportDiffered"] = rec["selfReportDiffered"]
        status = ("unmeasured" if not r["measured"]
                  else "refuted" if r["outOfScopeWrites"] else "proposed")
        detail["files"] = len(rec["filesTouched"])
        ev = _span(run.run_id, "invoke_agent arbeitsplan:candidate-builder", f"{phase}:{cid}", status, detail)
        problem = _event_problem(run, ev)
        if problem:
            raise run_record.RecordError(f"nothing written -- {problem}")
        records.append(rec)
        events.append(ev)
    notes = []
    for rec, ev in zip(records, events, strict=True):
        _write_once(run.dir / "candidates" / f"{rec['candidateId']}.json", rec)
        run.append(ev)
        note = f"candidates/{rec['candidateId']}.json written ({ev['status']})"
        if rec.get("diffSource") == "tree":
            note += ("; diff taken from the worktree -- the self-reported diff DIFFERED"
                     if rec["selfReportDiffered"] else "; diff taken from the worktree, matching the report")
        notes.append(note)
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

    def refused(fn) -> bool:
        try:
            fn()
        except run_record.RecordError:
            return True
        return False

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

            # A result is recorded whole or not at all: an oversized SECOND event
            # used to leave the first appended and no candidate/referee file written.
            wide_rid = "ap-t-13"
            wide = run_record.open_run(PLUGIN, wide_rid)
            before = len(wide.events())
            oversized = {"events": [
                _span(wide_rid, "phase build", "build", "opened"),
                _span(wide_rid, "invoke_agent arbeitsplan:candidate-referee", "build:c9", "accepted",
                      {"perCriterion": [{"id": f"w{i}", "met": True, "evidence": "e" * 200} for i in range(40)]}),
                _span(wide_rid, "phase build", "build", "closed")],
                "carry": {"build": {"candidates": [{"candidateId": "c9", "measured": True, "diff": "d"}]}}}
            ok("a result holding an oversized event is refused", refused(lambda: cmd_workflow(wide, oversized)))
            ok("...and NOTHING of it is recorded: no event, no candidate file",
               len(wide.events()) == before and not (wide.dir / "candidates" / "c9.json").exists())

            # The pre-check is calibrated against run_record itself, at the boundary.
            def padded(span_id: str, extra: int) -> dict:
                ev = {**_span(wide_rid, "evaluation", "edge", "accepted"), "span_id": span_id, "detail": {"pad": ""}}
                base = len((json.dumps({"kind": "event", "at": "0000-00-00T00:00:00+00:00", **ev},
                                       separators=(",", ":"), sort_keys=True) + "\n").encode())
                return {**ev, "detail": {"pad": "x" * (run_record.MAX_LINE - base + extra)}}

            fits = padded(f"{wide_rid}.edge.fits", 0)
            over = padded(f"{wide_rid}.edge.over", 1)
            ok("pre-check and run_record agree: exactly MAX_LINE bytes is accepted by both",
               _event_problem(wide, fits) is None and not refused(lambda: wide.append(fits)))
            ok("pre-check and run_record agree: one byte more is refused by both",
               _event_problem(wide, over) is not None and refused(lambda: wide.append(over)))

            # finish: the end marker sweep_artifacts.py waits for, earned or refused.
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

            # referee: an IN-SESSION run's batches reach rounds.py, and the rules fire.
            ins = run_record.open_run(PLUGIN, "ap-t-12")

            def verdict(cid: str, word: str, unmet: list) -> dict:
                return {"candidateId": cid, "verdict": word,
                        "perCriterion": [{"id": k, "met": k not in unmet, "evidence": "e"} for k in ("a1", "a2")]}

            ok("referee refuses a phase never opened in run.jsonl",
               refused(lambda: cmd_referee(ins, "referee-w1", [verdict("c1", "rejected", ["a2"])])))
            ins.append(_span("ap-t-12", "phase referee-w1", "referee-w1", "opened"))
            ok("referee refuses a verdict outside the referee vocabulary, writing nothing",
               refused(lambda: cmd_referee(ins, "referee-w1", [verdict("c1", "rejected", ["a2"]),
                                                              verdict("c2", "meh", ["a2"])]))
               and not (ins.dir / "referee").exists())
            ok("referee refuses a verdict with no perCriterion",
               refused(lambda: cmd_referee(ins, "referee-w1", {"candidateId": "c1", "verdict": "accepted"})))
            cmd_referee(ins, "referee-w1", [verdict("c1", "rejected", ["a2"]), verdict("c2", "rejected", ["a2"])])
            ok("an in-session batch writes the flat record and its phase twin",
               (ins.dir / "referee" / "c1.json").is_file() and (ins.dir / "referee" / "referee-w1" / "c2.json").is_file())
            ok("a (phase, candidate) verdict is written once",
               refused(lambda: cmd_referee(ins, "referee-w1", [verdict("c1", "accepted", [])])))
            ins.append(_span("ap-t-12", "phase referee-w1", "referee-w1", "closed"))
            ins.append(_span("ap-t-12", "phase referee-w2", "referee-w2", "opened"))
            cmd_referee(ins, "referee-w2", [verdict("c1", "accepted", []), verdict("c2", "rejected", ["a1"])])
            twin = ins.dir / "referee" / "referee-w2" / "c1.json"
            ok("a second phase reusing c1 keeps the flat record first-come",
               json.loads((ins.dir / "referee" / "c1.json").read_text())["verdict"] == "rejected"
               and twin.is_file() and json.loads(twin.read_text())["verdict"] == "accepted")
            ins.append(_span("ap-t-12", "phase referee-w2", "referee-w2", "closed"))
            cmd_phase_output(ins, "adjudicate", {"verdict": "hold", "round": {"outcome": "advanced", "blocking": "b1"}})

            rounds_py = Path(__file__).resolve().parent / "rounds.py"
            rec = subprocess.run([sys.executable, str(rounds_py), "record", "--run", "ap-t-12"],
                                 capture_output=True, text=True, cwd=raw)
            try:
                rs = json.loads(rec.stdout)
            except ValueError:
                rs = []
            ok("rounds.py record sees both in-session referee phases, in order",
               [r.get("phase") for r in rs] == ["referee-w1", "referee-w2"])
            ok("round 1 carries its two rejections on a2 and accepted nobody",
               len(rs) == 2 and rs[0]["accepted"] == [] and sorted(x["criterion"] for x in rs[0]["rejections"]) == ["a2", "a2"])
            ok("round 2 carries its own verdicts and the adjudicator's judge",
               len(rs) == 2 and rs[1]["accepted"] == ["c1"] and rs[1]["judge"] == {"outcome": "advanced", "blocking": "b1"})
            first = Path(raw) / "round1.json"
            first.write_text(json.dumps(rs[:1]))
            dec = subprocess.run([sys.executable, str(rounds_py), "decide", "--rounds", str(first)],
                                 capture_output=True, text=True, cwd=raw)
            ok("#78 now fires on an in-session run: ROUTE SYNTHESIZE criterion=a2",
               dec.stdout.strip() == "ROUTE SYNTHESIZE criterion=a2")
            ins.append(_span("ap-t-12", "phase referee-w3", "referee-w3", "opened"))
            big = {"candidateId": "c3", "verdict": "accepted",
                   "perCriterion": [{"id": f"w{i}", "met": True, "evidence": "x" * 120} for i in range(40)]}
            cmd_referee(ins, "referee-w3", [big])
            ok("a verdict with 40 long-evidence criteria is recorded (summary event, full record on disk)",
               len(json.loads((ins.dir / "referee" / "referee-w3" / "c3.json").read_text())["perCriterion"]) == 40)
            ok("referee refuses a run that has already ended",
               refused(lambda: cmd_referee(landed, "land", [verdict("c9", "accepted", [])])))

            # candidate: an IN-SESSION builder batch reaches candidates/<id>.json.
            cs = run_record.open_run(PLUGIN, "ap-t-14")

            def built(cid: str, diff: str | None = "diff --git a/x b/x\n", measured: bool = True) -> dict:
                return {"candidateId": cid, "angle": f"angle-{cid}", "measured": measured, "diff": diff,
                        "filesTouched": ["x"] if measured else [], "outOfScopeWrites": [],
                        "checks": [{"id": "a1", "command": "true", "exit": 0}] if measured else [],
                        "rationale": "r", "flaggedInstruction": None}

            ok("candidate refuses a phase never opened in run.jsonl",
               refused(lambda: cmd_candidate(cs, "build", [built("c1")])))
            cs.append(_span("ap-t-14", "phase build", "build", "opened"))
            ok("candidate refuses a result with no angle, writing nothing from its batch",
               refused(lambda: cmd_candidate(cs, "build", [built("c1"), {**built("c2"), "angle": ""}]))
               and not (cs.dir / "candidates").exists())
            ok("candidate refuses a measured result with no diff",
               refused(lambda: cmd_candidate(cs, "build", built("c1", diff=None))))
            ok("candidate refuses checks whose exit is not an int",
               refused(lambda: cmd_candidate(cs, "build", {**built("c1"), "checks": [{"id": "a1", "command": "t", "exit": "0"}]})))
            ok("candidate refuses a result missing outOfScopeWrites",
               refused(lambda: cmd_candidate(cs, "build", {k: v for k, v in built("c1").items() if k != "outOfScopeWrites"})))
            cmd_candidate(cs, "build", [built("c1"), built("c3", diff=None, measured=False)])
            c1 = json.loads((cs.dir / "candidates" / "c1.json").read_text())
            ok("a batch writes one record per candidate, tagged with its phase",
               c1["phase"] == "build" and c1["diff"] == "diff --git a/x b/x\n"
               and (cs.dir / "candidates" / "c3.json").is_file())
            ok("an unmeasured result is recorded as unmeasured, not as a failure",
               [e["status"] for e in cs.events() if e["node_id"] == "build:c3"] == ["unmeasured"])
            ok("a candidate is written once",
               refused(lambda: cmd_candidate(cs, "build", {**built("c1"), "diff": "OVERWRITE"}))
               and "OVERWRITE" not in (cs.dir / "candidates" / "c1.json").read_text())

            tree = Path(raw) / "wt"
            tree.mkdir()

            def git(*argv: str) -> None:
                subprocess.run(["git", "-C", str(tree), *argv], check=True, capture_output=True)

            git("init", "-q")
            (tree / "kept.txt").write_text("one\n")
            git("add", "kept.txt")
            git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "base")
            (tree / "kept.txt").write_text("two\n")
            (tree / "new.txt").write_text("created\n")
            ok("--tree refuses a list, whose worktrees it cannot tell apart",
               refused(lambda: cmd_candidate(cs, "build", [built("c4"), built("c5")], tree)))
            cmd_candidate(cs, "build", {**built("c4"), "diff": "diff --git a/kept.txt\n[... elided ...]\n"}, tree)
            c4 = json.loads((cs.dir / "candidates" / "c4.json").read_text())
            ok("--tree replaces the self-reported diff with the worktree's, untracked files included",
               c4["diffSource"] == "tree" and "+two" in c4["diff"] and "+created" in c4["diff"]
               and "elided" not in c4["diff"] and sorted(c4["filesTouched"]) == ["kept.txt", "new.txt"])
            ok("--tree notes that the paraphrased self-report differed", c4["selfReportDiffered"] is True)
            cmd_candidate(cs, "build", {**built("c6"), "diff": c4["diff"]}, tree)
            ok("--tree notes a self-report that matched",
               json.loads((cs.dir / "candidates" / "c6.json").read_text())["selfReportDiffered"] is False)
            git("checkout", "-q", "--", "kept.txt")
            git("rm", "-q", "--cached", "new.txt")
            (tree / "new.txt").unlink()
            ok("--tree refuses a measured report over a worktree with no diff",
               refused(lambda: cmd_candidate(cs, "build", built("c7"), tree))
               and not (cs.dir / "candidates" / "c7.json").exists())
            ok("candidate refuses a run that has already ended",
               refused(lambda: cmd_candidate(landed, "land", built("c9"))))
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
    ca = sub.add_parser("candidate")
    ca.add_argument("--run", required=True)
    ca.add_argument("--phase", required=True)
    ca.add_argument("--result", required=True, help="one candidate-builder result, or a JSON list of them")
    ca.add_argument("--tree", type=Path, help="the candidate's worktree: its real diff replaces the self-reported one")
    rf = sub.add_parser("referee")
    rf.add_argument("--run", required=True)
    rf.add_argument("--phase", required=True)
    rf.add_argument("--verdict", required=True, help="one referee verdict, or a JSON list of them")
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
        src = (args.result if args.cmd in ("workflow", "candidate")
               else args.verdict if args.cmd == "referee" else args.output)
        try:
            data = json.loads(Path(src).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            print(f"cannot read {src}: {exc}", file=sys.stderr)
            return 2
        if args.cmd == "workflow":
            notes = cmd_workflow(run, data)
        elif args.cmd == "candidate":
            notes = cmd_candidate(run, args.phase, data, args.tree)
        elif args.cmd == "referee":
            notes = cmd_referee(run, args.phase, data)
        else:
            notes = cmd_phase_output(run, args.phase, data)
        for n in notes:
            print(n)
        return 0
    except run_record.RecordError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
