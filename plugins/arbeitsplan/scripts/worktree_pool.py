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
    candidates = []
    if kind in ("fanout-redundant", "fanout-blind"):
        for i in range(1, int(ph.get("fanOut", 0)) + 1):
            cid = f"c{i}"
            candidates.append({"id": cid, "worktree": str((worktree_root(run_id) / cid).resolve())})

    lock = {
        "runId": run_id,
        "phase": args.phase,
        "kind": kind,
        # Only a single-writer phase may touch the shared tree. During a fan-out
        # every candidate writes inside its own worktree and exactly one diff is
        # applied afterwards -- that is what makes a merge conflict impossible.
        "sharedTreeWritable": kind == "single-writer",
        "writeScope": spec["writeScope"],
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
    print(f"lock open: run {run_id}, phase '{args.phase}' ({kind}), "
          f"{len(candidates)} candidate slot(s), shared tree "
          f"{'writable' if lock['sharedTreeWritable'] else 'CLOSED'}")
    return 0


def cmd_close(args) -> int:
    if not LOCK.exists():
        print("no lock open")
        return 0
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
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
    made, failed = [], []
    for i in range(1, args.count + 1):
        cid = f"c{i}"
        path = root / cid
        branch = f"arbeitsplan/{run_id}/{cid}"
        if path.exists():
            print(f"  {cid}: already exists at {path}")
            made.append(cid)
            continue
        r = git("worktree", "add", "-b", branch, str(path))
        if r.returncode != 0:
            # A candidate whose worktree could not be created is UNMEASURED, not
            # failed. Reporting it as failed would feed the breaker a reading of
            # the environment instead of the work.
            failed.append((cid, r.stderr.strip().splitlines()[-1] if r.stderr.strip() else "git worktree add failed"))
            print(f"  {cid}: UNMEASURED -- {failed[-1][1]}")
        else:
            made.append(cid)
            print(f"  {cid}: {path} on {branch}")
    print(f"{len(made)} worktree(s) ready, {len(failed)} unmeasured")
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
    return 0


def cmd_selftest(args) -> int:
    import tempfile
    spec = {
        "runId": "ap-t-1", "writeScope": ["src/**"],
        "budget": {"totalDispatches": 7, "wallClockMinutes": 25},
        "phases": [
            {"id": "build", "kind": "fanout-redundant", "fanOut": 3},
            {"id": "land", "kind": "single-writer"},
        ],
    }
    fails = []
    import os  # only for chdir; Path has no equivalent, by design
    with tempfile.TemporaryDirectory() as raw:
        cwd = Path.cwd()
        try:
            os.chdir(raw)
            Path("spec.json").write_text(json.dumps(spec))
            cmd_open(argparse.Namespace(spec="spec.json", phase="build"))
            lock = json.loads(LOCK.read_text())
            for name, ok in [
                ("fan-out phase closes the shared tree", lock["sharedTreeWritable"] is False),
                ("fan-out phase lists one slot per candidate", len(lock["candidates"]) == 3),
                ("writeScope is carried from the spec", lock["writeScope"] == ["src/**"]),
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
            ]:
                print(f"  {'ok  ' if ok else 'FAIL'} {name}")
                if not ok:
                    fails.append(name)
            cmd_close(argparse.Namespace())
            ok = not LOCK.exists()
            print(f"  {'ok  ' if ok else 'FAIL'} close removes the lock")
            if not ok:
                fails.append("close")
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

    p = sub.add_parser("close", help="release the lock")
    p.set_defaults(fn=cmd_close)

    p = sub.add_parser("create", help="create one worktree per candidate")
    p.add_argument("--spec", required=True)
    p.add_argument("--count", type=int, required=True)
    p.set_defaults(fn=cmd_create)

    p = sub.add_parser("destroy", help="delete losing worktrees and their branches")
    p.add_argument("--run", required=True)
    p.add_argument("--keep", nargs="*", default=[])
    p.set_defaults(fn=cmd_destroy)

    p = sub.add_parser("selftest", help="planted-defect selftest")
    p.set_defaults(fn=cmd_selftest)

    args = parser.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
