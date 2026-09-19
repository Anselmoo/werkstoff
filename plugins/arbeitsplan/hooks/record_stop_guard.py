#!/usr/bin/env python3
"""Stop hook: refuse ONE completion while an arbeitsplan phase has not recorded how it ended.

usage: record_stop_guard.py   (no arguments; the Stop event arrives as JSON on stdin)
  Its calibration is plugins/arbeitsplan/hooks/test_record_stop_guard.py.

A session that says "done" while run_scope.json still arms a phase with no
terminal event in run.jsonl leaves exactly the trace this repository keeps
finding: a run that halted and a run that was abandoned look the same. Neither
of the tools surveyed enforces its execution record with a hook; this is that
missing half, and it is deliberately small.

  * INERT unless analysis/arbeitsplan/run_scope.json exists.
  * BLOCKS AT MOST ONCE. When `stop_hook_active` is true the stop is already a
    continuation this hook caused, so it allows -- a Stop hook that blocks every
    time traps the session, and the harness caps it anyway.
  * Blocks with BOTH exit 2 + stderr AND stdout JSON {"decision": "block",
    "reason": ...}, so the reason reaches Claude either way.
  * An unreadable record blocks once too, naming the escape hatch
    ARBEITSPLAN_DISABLE_GUARD=1 -- never read as "nothing is open".

The reason names the two legal moves: record the phase closed, or close the lock
with --halt and a specific reason.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import NoReturn

HERE = Path(__file__).resolve().parent
# Named, not a literal: ruff's target is py312, so it reads a literal version
# check as dead code. It is not -- a hook runs under whatever python3 is on PATH.
MIN_PYTHON = (3, 11)
sys.path.insert(0, str(HERE.parent / "scripts"))


def block(reason: str) -> NoReturn:
    print(json.dumps({"decision": "block", "reason": reason}))
    print(reason, file=sys.stderr)
    sys.exit(2)


def main() -> None:
    if os.environ.get("ARBEITSPLAN_DISABLE_GUARD") == "1":
        sys.exit(0)
    try:
        event = json.loads(sys.stdin.read() or "{}")
    except ValueError:
        event = {}
    if event.get("stop_hook_active"):
        sys.exit(0)  # one nudge only; this stop is already the continuation
    cwd = Path(event.get("cwd") or Path.cwd())
    lock_path = cwd / "analysis" / "arbeitsplan" / "run_scope.json"
    if not lock_path.is_file():
        sys.exit(0)  # inert: no arbeitsplan phase is armed
    if sys.version_info < MIN_PYTHON:
        block(f"arbeitsplan needs Python >= 3.11 to read its run record; this hook ran under "
              f"{sys.version.split()[0]} ({sys.executable}). Put a newer python3 first on PATH, "
              "or set ARBEITSPLAN_DISABLE_GUARD=1.")
    try:
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
        run_id, phase = lock["runId"], lock["phase"]
        import run_record  # vendored beside the scripts; imported late so an inert hook never needs it

        log = run_record.run_dir("arbeitsplan", run_id, cwd) / "run.jsonl"
        if not log.is_file():
            block(f"arbeitsplan: phase {phase!r} of run {run_id!r} is armed (run_scope.json) but the "
                  f"run has no run.jsonl, so nothing records how it ended. Record it -- "
                  f"`python3 plugins/arbeitsplan/scripts/record_event.py phase --run {run_id} "
                  f"--phase {phase} --status closed` -- or close with "
                  f"`worktree_pool.py close --halt \"<reason>\"`.")
        events = run_record.open_run("arbeitsplan", run_id, cwd).events()
    except SystemExit:
        raise
    except Exception as exc:  # any failure to read is reported, never read as "clear"
        block(f"arbeitsplan: the run record could not be read ({type(exc).__name__}: {exc}), so "
              "whether a phase is still open is unknown. Fix the record, or set "
              "ARBEITSPLAN_DISABLE_GUARD=1 if this repository is no longer running arbeitsplan.")
    if any(e.get("node_id") == phase and e.get("status") in ("closed", "halted") for e in events):
        sys.exit(0)
    block(f"arbeitsplan: phase {phase!r} of run {run_id!r} is still armed and recorded no terminal "
          f"event, so stopping now leaves a run nobody can tell from an abandoned one. Either "
          f"record it closed -- `python3 plugins/arbeitsplan/scripts/record_event.py phase --run "
          f"{run_id} --phase {phase} --status closed` then `worktree_pool.py close` -- or record "
          f"why it stopped: `python3 plugins/arbeitsplan/scripts/worktree_pool.py close --halt "
          f"\"<the specific reason>\"`.")


if __name__ == "__main__":
    main()
