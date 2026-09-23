#!/usr/bin/env python3
"""Open and close the run-scope lock, and manage candidate worktrees.

usage: worktree_pool.py [-h] {open,close,create,destroy,selftest} ...

The lock at analysis/arbeitsplan/run_scope.json is what ARMS arbeitsplan's
PreToolUse guard. It is a PER-DISPATCH lock describing the phase in flight, not
a durable repo-level flag -- that distinction is load-bearing rather than
stylistic. A guard in this repository once gated on repo-level state and swept
every edit in the session, from any plugin, into its gate; parallel writers are
exactly the case that breaks repo-level gating, and parallel writers are this
plugin's entire premise.

Closing the lock is deliberately a separate, explicit act. A stale lock denies
every write, which is the safe direction.

Exit: 0 ok, 1 refused, 2 bad input.

STDLIB ONLY -- it must run under a bare system python3.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import land_candidate  # subtract_referee_owned: the seam a fan-out phase's lock
                       # and compile_spec.py's AP-REFOWNED-OUTSIDE-SCOPE share
import run_record  # vendored copy of tools/run-record/run_record.py

LOCK = Path("analysis/arbeitsplan/run_scope.json")


def load_spec(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def phase_of(spec: dict, phase_id: str) -> dict:
    for ph in spec.get("phases", []):
        if ph.get("id") == phase_id:
            return ph
    raise SystemExit(f"worktree_pool.py: spec has no phase {phase_id!r}")


def worktree_root(run_id: str) -> Path:
    return Path(".arbeitsplan") / run_id


def cmd_open(args) -> int:
    spec = load_spec(args.spec)
    ph = phase_of(spec, args.phase)
    run_id = spec["runId"]
    kind = ph.get("kind")
    # The plan-node stop, made unconstructible. With this lock open a plan-mode
    # session has no legal write: the guard denies its plan file and plan mode
    # denies everything else. So a plan-mode phase never runs under a lock --
    # close, run it, re-open the next phase. Loop state lives in the skill.
    if ph.get("mode") == "plan":
        print(f"REFUSED: phase {args.phase!r} is mode 'plan'. A run-scope lock and plan mode "
              "together leave no legal write, so no lock is opened for it. Close any held "
              "lock (worktree_pool.py close), run this phase in plan mode, then open the "
              "next phase.", file=sys.stderr)
        return 1
    candidates = []
    if kind in ("fanout-redundant", "fanout-blind"):
        for i in range(1, int(ph.get("fanOut", 0)) + 1):
            cid = f"c{i}"
            candidates.append({"id": cid, "worktree": str((worktree_root(run_id) / cid).resolve())})

    # refereeOwned (#77): a fan-out phase's lock opens with writeScope already
    # NARROWED, so the guard's ordinary matches(probe, writeScope) check enforces
    # the subtraction too, with no change to the guard itself -- it always just
    # read whatever writeScope this lock declares. A referee-fixture phase (and a
    # single-writer landing phase) keeps the FULL scope: the fixture phase is the
    # one thing that is SUPPOSED to write those paths, before any candidate
    # exists at all.
    write_scope = spec["writeScope"]
    if kind in ("fanout-redundant", "fanout-blind", "fanout-readonly"):
        write_scope = land_candidate.subtract_referee_owned(
            write_scope, spec.get("refereeOwned") or [])

    lock = {
        "runId": run_id,
        "phase": args.phase,
        "kind": kind,
        # A single-writer landing phase and a referee-fixture phase are the only
        # two kinds that may touch the shared tree. During a fan-out every
        # candidate writes inside its own worktree and exactly one diff is
        # applied afterwards -- that is what makes a merge conflict impossible.
        "sharedTreeWritable": kind in ("single-writer", "referee-fixture"),
        "writeScope": write_scope,
        "candidates": candidates,
        "fanOut": ph.get("fanOut", 1),
        "budget": spec["budget"],
    }
    # run_scope.json is ONE repository-wide lock and the guard reads whatever it
    # finds. Overwriting it while another run's builders are still dispatching
    # silently re-pointed the guard at a different phase, scope, budget and
    # worktree list, so writes from the first run were judged against the
    # second's contract. A phase transition within the SAME run is the
    # legitimate case and still works.
    if LOCK.is_file():
        try:
            held = json.loads(LOCK.read_text(encoding="utf-8"))
        except ValueError:
            held = {}
        held_run = held.get("runId")
        if held_run and held_run != run_id:
            print(f"REFUSED: run '{held_run}' already holds {LOCK} (phase "
                  f"{held.get('phase')!r}). Opening run '{run_id}' over it would point the "
                  "guard at this run's scope and budget while the other run's builders are "
                  "still writing. Close the held run first: worktree_pool.py close",
                  file=sys.stderr)
            return 1

    LOCK.parent.mkdir(parents=True, exist_ok=True)
    LOCK.write_text(json.dumps(lock, indent=2) + "\n")
    # The phase boundary goes into the record at the moment it happens, so a phase
    # that later ends without saying how is visible as open -- see cmd_close.
    run_record.open_run("arbeitsplan", run_id).append({
        "trace_id": run_id, "span_id": f"{run_id}.lock.{args.phase}.opened",
        "parent_span_id": f"{run_id}.root", "span": f"phase {args.phase}",
        "node_id": args.phase, "status": "opened"})
    print(f"lock open: run {run_id}, phase '{args.phase}' ({kind}), "
          f"{len(candidates)} candidate slot(s), shared tree "
          f"{'writable' if lock['sharedTreeWritable'] else 'CLOSED'}")
    return 0


def cmd_close(args) -> int:
    if not LOCK.exists():
        print("no lock open")
        return 0
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    run_id, phase = lock.get("runId"), lock.get("phase")
    # A phase that ends without saying how is the shape this repository keeps
    # finding: a halt that left no trace is indistinguishable from an abandoned
    # run. So closing requires a terminal event for the phase -- closed, or a
    # halt with its reason, which --halt records here.
    if run_id and phase:
        try:
            run = run_record.open_run("arbeitsplan", run_id)
            halt = getattr(args, "halt", None)
            if halt:
                run.halt(halt, phase)
            terminal = {e["status"] for e in run.events()
                        if e["node_id"] == phase and e["status"] in ("closed", "halted")}
        except run_record.RecordError as exc:
            print(f"REFUSED: the run record cannot be read ({exc}); fix it before closing.",
                  file=sys.stderr)
            return 1
        if not terminal:
            print(f"REFUSED: phase {phase!r} of run {run_id!r} recorded no terminal event. Record "
                  f"how it ended first -- `record_event.py phase --run {run_id} --phase {phase} "
                  f"--status closed` -- or close with --halt \"<specific reason>\".",
                  file=sys.stderr)
            return 1
    LOCK.unlink()
    print(f"lock closed (was run {lock.get('runId')}, phase {lock.get('phase')!r})")
    return 0


def git(*a) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *a], capture_output=True, text=True)


def cmd_create(args) -> int:
    spec = load_spec(args.spec)
    run_id = spec["runId"]
    root = worktree_root(run_id)
    root.mkdir(parents=True, exist_ok=True)

    # base (#79): --phase names a fanout-redundant phase; if IT declares 'base',
    # every worktree this call creates starts from that base's promoted branch
    # (arbeitsplan/<runId>/base/<Q>) instead of HEAD -- a candidate stacked on a
    # prior wave's refereed winner must actually see that winner's tree, not a
    # fresh checkout that never had it. A phase without 'base' (or --phase
    # omitted entirely) behaves exactly as before: from HEAD.
    start_point = None
    if args.phase:
        ph = phase_of(spec, args.phase)
        base = ph.get("base")
        if base:
            start_point = f"arbeitsplan/{run_id}/base/{base}"
            check = git("rev-parse", "--verify", "-q", start_point)
            if check.returncode != 0:
                print(f"REFUSED: phase {args.phase!r} declares base {base!r}, but branch "
                      f"{start_point!r} has not been promoted. Promote {base!r}'s winner "
                      f"first: worktree_pool.py promote --run {run_id} --phase {base} "
                      "--candidate <id>", file=sys.stderr)
                return 1

    made, failed = [], []
    for i in range(1, args.count + 1):
        cid = f"c{i}"
        path = root / cid
        branch = f"arbeitsplan/{run_id}/{cid}"
        if path.exists():
            print(f"  {cid}: already exists at {path}")
            made.append(cid)
            continue
        cmd = ["worktree", "add", "-b", branch, str(path)]
        if start_point:
            cmd.append(start_point)
        r = git(*cmd)
        if r.returncode != 0:
            # A candidate whose worktree could not be created is UNMEASURED, not
            # failed. Reporting it as failed would feed the breaker a reading of
            # the environment instead of the work.
            failed.append((cid, r.stderr.strip().splitlines()[-1] if r.stderr.strip() else "git worktree add failed"))
            print(f"  {cid}: UNMEASURED -- {failed[-1][1]}")
        else:
            made.append(cid)
            origin = f" (from {start_point})" if start_point else ""
            print(f"  {cid}: {path} on {branch}{origin}")
    print(f"{len(made)} worktree(s) ready, {len(failed)} unmeasured")
    return 0


def cmd_promote(args) -> int:
    """Commit everything sitting in a candidate's worktree (untracked included)
    and point `arbeitsplan/<run>/base/<phase>` at that commit -- the ONE seam a
    later fanout-redundant phase's `base: <phase>` reads from. `--phase` names
    the phase whose winner this is, not the candidate's own id, so the branch a
    later `create --phase` looks for is named after the thing it stacks on."""
    run_id, phase_q, cid = args.run, args.phase, args.candidate
    path = worktree_root(run_id) / cid
    if not path.is_dir():
        print(f"REFUSED: no worktree at {path} for candidate {cid!r} of run {run_id!r}.",
              file=sys.stderr)
        return 1
    add = git("-C", str(path), "add", "-A")
    if add.returncode != 0:
        print(f"REFUSED: 'git add -A' failed in {path}: {add.stderr.strip()}", file=sys.stderr)
        return 1
    commit = git("-C", str(path), "-c", "user.email=arbeitsplan@local",
                "-c", "user.name=arbeitsplan", "commit", "--allow-empty",
                "-m", f"arbeitsplan {run_id}: promote {cid} as base for {phase_q}")
    if commit.returncode != 0:
        print(f"REFUSED: commit failed in {path}: {commit.stderr.strip()}", file=sys.stderr)
        return 1
    sha = git("-C", str(path), "rev-parse", "HEAD").stdout.strip()
    base_ref = f"arbeitsplan/{run_id}/base/{phase_q}"
    mv = git("branch", "-f", base_ref, sha)
    if mv.returncode != 0:
        print(f"REFUSED: could not point {base_ref} at {sha}: {mv.stderr.strip()}",
              file=sys.stderr)
        return 1
    print(f"promoted {cid}: {base_ref} -> {sha}")
    return 0


def cmd_destroy(args) -> int:
    root = worktree_root(args.run)
    removed = []
    for path in sorted(root.glob("c*")):
        if args.keep and path.name in args.keep:
            print(f"  {path.name}: kept")
            continue
        git("worktree", "remove", "--force", str(path))
        git("branch", "-D", f"arbeitsplan/{args.run}/{path.name}")
        removed.append(path.name)
        print(f"  {path.name}: removed (worktree and branch)")
    print(f"{len(removed)} loser(s) deleted. Nothing was merged.")
    # --bases (#79): base branches survive an ordinary destroy on purpose -- a
    # later wave may still need arbeitsplan/<run>/base/<phase> to stack the next
    # fan-out on. Only an explicit --bases sweeps them, once the whole run (every
    # wave) is actually done with them.
    if getattr(args, "bases", False):
        listed = git("branch", "--list", f"arbeitsplan/{args.run}/base/*")
        bases = [ln.strip().lstrip("* ").strip() for ln in listed.stdout.splitlines() if ln.strip()]
        for b in bases:
            git("branch", "-D", b)
            print(f"  {b}: base branch removed")
        print(f"{len(bases)} base branch(es) removed.")
    return 0


def cmd_selftest(args) -> int:
    import tempfile
    spec = {
        "runId": "ap-t-1", "writeScope": ["src/**", "oracle/**"],
        "refereeOwned": ["oracle/spec.txt"],
        "budget": {"totalDispatches": 7, "wallClockMinutes": 25},
        "phases": [
            {"id": "oracle", "kind": "referee-fixture"},
            {"id": "build", "kind": "fanout-redundant", "fanOut": 3},
            {"id": "land", "kind": "single-writer"},
            {"id": "contract", "kind": "single-writer", "mode": "plan"},
        ],
    }
    fails = []
    import os  # only for chdir; Path has no equivalent, by design
    with tempfile.TemporaryDirectory() as raw:
        cwd = Path.cwd()
        try:
            os.chdir(raw)
            Path("spec.json").write_text(json.dumps(spec))
            cmd_open(argparse.Namespace(spec="spec.json", phase="oracle"))
            lock = json.loads(LOCK.read_text())
            for name, ok in [
                ("referee-fixture phase opens the shared tree", lock["sharedTreeWritable"] is True),
                ("referee-fixture phase keeps the FULL writeScope (it is the writer)",
                    lock["writeScope"] == ["src/**", "oracle/**"]),
            ]:
                print(f"  {'ok  ' if ok else 'FAIL'} {name}")
                if not ok:
                    fails.append(name)
            cmd_open(argparse.Namespace(spec="spec.json", phase="build"))
            lock = json.loads(LOCK.read_text())
            for name, ok in [
                ("fan-out phase closes the shared tree", lock["sharedTreeWritable"] is False),
                ("fan-out phase lists one slot per candidate", len(lock["candidates"]) == 3),
                # refereeOwned (#77): 'oracle/**' overlaps the declared refereeOwned
                # path 'oracle/spec.txt', so a fan-out phase's lock drops it whole --
                # only 'src/**' survives the subtraction.
                ("a fan-out phase's writeScope is NARROWED by refereeOwned",
                    lock["writeScope"] == ["src/**"]),
                ("budget is carried from the spec", lock["budget"]["totalDispatches"] == 7),
            ]:
                print(f"  {'ok  ' if ok else 'FAIL'} {name}")
                if not ok:
                    fails.append(name)
            cmd_open(argparse.Namespace(spec="spec.json", phase="land"))
            lock = json.loads(LOCK.read_text())
            for name, ok in [
                ("single-writer phase opens the shared tree", lock["sharedTreeWritable"] is True),
                ("single-writer phase has no candidate slots", lock["candidates"] == []),
                ("single-writer phase keeps the FULL writeScope (it lands the diff)",
                    lock["writeScope"] == ["src/**", "oracle/**"]),
            ]:
                print(f"  {'ok  ' if ok else 'FAIL'} {name}")
                if not ok:
                    fails.append(name)
            rc = cmd_close(argparse.Namespace(halt=None))
            ok = rc == 1 and LOCK.exists()
            print(f"  {'ok  ' if ok else 'FAIL'} close refuses a phase that recorded no terminal event")
            if not ok:
                fails.append("close without terminal event")
            rc = cmd_close(argparse.Namespace(halt="selftest: stopping here on purpose"))
            ok = rc == 0 and not LOCK.exists() and any(
                e["status"] == "halted" for e in run_record.open_run("arbeitsplan", "ap-t-1").events())
            print(f"  {'ok  ' if ok else 'FAIL'} close --halt records the halt, then closes")
            if not ok:
                fails.append("close --halt")
            rc = cmd_open(argparse.Namespace(spec="spec.json", phase="contract"))
            ok = rc == 1 and not LOCK.exists()
            print(f"  {'ok  ' if ok else 'FAIL'} a plan-mode phase opens no lock")
            if not ok:
                fails.append("plan-mode phase")
            ok = not LOCK.exists()
            print(f"  {'ok  ' if ok else 'FAIL'} close removes the lock")
            if not ok:
                fails.append("close")
        finally:
            os.chdir(cwd)

    # create --phase / promote / destroy --bases (#79). A real git repo is
    # needed here -- these commands run `git worktree`/`git branch`, and
    # `create --phase` must actually resolve `arbeitsplan/<R>/base/<Q>` before
    # trusting it.
    with tempfile.TemporaryDirectory() as raw:
        cwd = Path.cwd()
        try:
            os.chdir(raw)
            Path("seed.txt").write_text("seed\n")
            for c in (["git", "init", "-q"], ["git", "add", "-A"],
                      ["git", "-c", "user.email=p@p", "-c", "user.name=p",
                       "commit", "-qm", "seed"]):
                subprocess.run(c, capture_output=True)
            run_id = "ap-t-base"
            spec = {
                "runId": run_id, "writeScope": ["**"],
                "budget": {"totalDispatches": 5, "wallClockMinutes": 5},
                "phases": [
                    {"id": "build-a", "kind": "fanout-redundant", "fanOut": 1},
                    {"id": "build-b", "kind": "fanout-redundant", "fanOut": 1, "base": "build-a"},
                ],
            }
            Path("spec.json").write_text(json.dumps(spec))
            base_ref = f"arbeitsplan/{run_id}/base/build-a"

            rc = cmd_create(argparse.Namespace(spec="spec.json", phase="build-b", count=1))
            ok = rc == 1 and not (worktree_root(run_id) / "c1").exists()
            print(f"  {'ok  ' if ok else 'FAIL'} create --phase with an unpromoted base is "
                  "refused, nothing created")
            if not ok:
                fails.append("create --phase refuses an unpromoted base")

            rc = cmd_create(argparse.Namespace(spec="spec.json", phase=None, count=1))
            ok = rc == 0 and (worktree_root(run_id) / "c1").is_dir()
            print(f"  {'ok  ' if ok else 'FAIL'} plain create (no --phase) still works")
            if not ok:
                fails.append("plain create")
            if ok:
                (worktree_root(run_id) / "c1" / "winner.txt").write_text("winner\n")

            rc = cmd_promote(argparse.Namespace(run=run_id, phase="build-a", candidate="c1"))
            ls = subprocess.run(["git", "ls-tree", "-r", "--name-only", base_ref],
                                capture_output=True, text=True).stdout
            ok = rc == 0 and "winner.txt" in ls
            print(f"  {'ok  ' if ok else 'FAIL'} promote commits the untracked file and moves "
                  f"{base_ref}")
            if not ok:
                fails.append("promote")

            rc = cmd_destroy(argparse.Namespace(run=run_id, keep=[], bases=False))
            survives = subprocess.run(["git", "rev-parse", "--verify", "-q", base_ref],
                                      capture_output=True).returncode == 0
            print(f"  {'ok  ' if survives else 'FAIL'} destroy without --bases leaves the base "
                  "branch alone")
            if not survives:
                fails.append("destroy keeps base")

            rc = cmd_create(argparse.Namespace(spec="spec.json", phase="build-b", count=1))
            stacked = (worktree_root(run_id) / "c1" / "winner.txt").is_file()
            print(f"  {'ok  ' if rc == 0 and stacked else 'FAIL'} create --phase with a "
                  "promoted base starts from it")
            if not (rc == 0 and stacked):
                fails.append("create --phase from a promoted base")

            cmd_destroy(argparse.Namespace(run=run_id, keep=[], bases=True))
            gone = subprocess.run(["git", "branch", "--list", f"arbeitsplan/{run_id}/*"],
                                  capture_output=True, text=True).stdout.strip()
            print(f"  {'ok  ' if not gone else 'FAIL'} destroy --bases leaves no "
                  f"arbeitsplan/{run_id}/* branch")
            if gone:
                fails.append("destroy --bases")
        finally:
            os.chdir(cwd)

    print()
    if fails:
        print(f"SELFTEST FAILED ({len(fails)}): " + ", ".join(fails))
        return 1
    print("selftest passed")
    return 0


def main(argv: list) -> int:
    parser = argparse.ArgumentParser(
        prog="worktree_pool.py",
        description="Open/close arbeitsplan's run-scope lock and manage candidate worktrees.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("open", help="arm the guard for one phase")
    p.add_argument("--spec", required=True)
    p.add_argument("--phase", required=True)
    p.set_defaults(fn=cmd_open)

    p = sub.add_parser("close", help="release the lock (the phase must have recorded how it ended)")
    p.add_argument("--halt", help="record a halt with this reason, then close")
    p.set_defaults(fn=cmd_close)

    p = sub.add_parser("create", help="create one worktree per candidate")
    p.add_argument("--spec", required=True)
    p.add_argument("--phase", help="if this phase declares 'base', worktrees start from its "
                                   "promoted branch instead of HEAD; omitted (or a phase with "
                                   "no base) behaves exactly as before")
    p.add_argument("--count", type=int, required=True)
    p.set_defaults(fn=cmd_create)

    p = sub.add_parser("promote", help="commit a candidate worktree and point its phase's "
                                       "base branch at it")
    p.add_argument("--run", required=True)
    p.add_argument("--phase", required=True, help="the fanout-redundant phase this candidate won")
    p.add_argument("--candidate", required=True)
    p.set_defaults(fn=cmd_promote)

    p = sub.add_parser("destroy", help="delete losing worktrees and their branches")
    p.add_argument("--run", required=True)
    p.add_argument("--keep", nargs="*", default=[])
    p.add_argument("--bases", action="store_true",
                   help="also delete every arbeitsplan/<run>/base/* branch; without it they "
                        "survive for a later wave to stack on")
    p.set_defaults(fn=cmd_destroy)

    p = sub.add_parser("selftest", help="planted-defect selftest")
    p.set_defaults(fn=cmd_selftest)

    args = parser.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
