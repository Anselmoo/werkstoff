#!/usr/bin/env python3
"""Advance a cupertino-repair run through its gates. Every gate the guard reads is written here.

usage: repair_state.py [-h] {begin,objective,approve,start-item,finish-item,end,status} ...

  begin [RUN_ID]          start a run (default id: UTC timestamp); writes .cupertino/repair/ACTIVE
  objective               validate .cupertino/repair/<run>/objective.json (written by the session)
  approve                 validate changeset.json against the objective, then bind approval to its
                          sha256 -- editing the changeset afterwards voids the approval
  start-item ID           mark one approved item active; the guard lets Write/Edit touch only its paths
  finish-item ID          clear the active item
  end [--abandon]         clear ACTIVE (after verify.py wrote a verdict, unless --abandon)
  status                  print the run's gate state as JSON

Run `approve` only after the user has seen the changeset and said yes; the skill says so,
and the hash binding means a changeset edited after that "yes" is not approved.

Exit: 0 ok; 1 a gate refused (message on stderr); 2 bad usage.
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from repair_lib import (  # noqa: E402
    RepairError,
    active_run,
    approved_changeset,
    changeset_hash,
    check_objective_frozen,
    project_root,
    read_json,
    repair_dir,
    run_dir,
    validate_changeset,
    validate_objective,
)


def _run(root: Path) -> str:
    run_id = active_run(root)
    if not run_id:
        raise RepairError("no repair run is active -- run `repair_state.py begin` (or preflight_repair.py) first")
    return run_id


def cmd_begin(root: Path, run_id: str | None) -> dict:
    current = active_run(root)
    if current:
        raise RepairError(f"run {current} is still active -- finish it with verify.py, or `end --abandon`")
    run_id = run_id or datetime.datetime.now(datetime.UTC).strftime("%Y%m%dT%H%M%SZ")
    rdir = run_dir(root, run_id)
    if rdir.exists():
        raise RepairError(f"run {run_id} already exists; pick a new id")
    rdir.mkdir(parents=True)
    (root / ".cupertino" / "flags").mkdir(parents=True, exist_ok=True)
    (repair_dir(root) / "ACTIVE").write_text(run_id + "\n", encoding="utf-8")
    return {"ok": True, "runId": run_id, "dir": str(rdir)}


def cmd_objective(root: Path) -> dict:
    run_id = _run(root)
    obj = read_json(run_dir(root, run_id) / "objective.json")
    validate_objective(obj)
    return {"ok": True, "runId": run_id, "acceptance": len(obj["acceptance"]), "mustPreserve": len(obj.get("mustPreserve", []))}


def cmd_approve(root: Path) -> dict:
    run_id = _run(root)
    rdir = run_dir(root, run_id)
    if not (rdir / "baseline" / "baseline.json").is_file():
        raise RepairError("no baseline yet -- run baseline.py before planning changes, so verify.py has something to compare against")
    check_objective_frozen(root, run_id)
    objective = read_json(rdir / "objective.json")
    validate_objective(objective)
    validate_changeset(read_json(rdir / "changeset.json"), objective)
    digest = changeset_hash(root, run_id)
    (rdir / "approved").write_text(digest + "\n", encoding="utf-8")
    return {"ok": True, "runId": run_id, "changesetSha256": digest}


def cmd_start_item(root: Path, item_id: str) -> dict:
    run_id = _run(root)
    changeset = approved_changeset(root, run_id)
    item = next((i for i in changeset["items"] if i["id"] == item_id), None)
    if item is None:
        raise RepairError(f"no item {item_id!r} in the approved changeset")
    active = run_dir(root, run_id) / "active-item"
    if active.is_file() and active.read_text(encoding="utf-8").strip() != item_id:
        raise RepairError(f"item {active.read_text(encoding='utf-8').strip()} is still active -- finish-item it first")
    active.write_text(item_id + "\n", encoding="utf-8")
    return {"ok": True, "runId": run_id, "item": item_id, "op": item["op"], "paths": item["paths"]}


def cmd_finish_item(root: Path, item_id: str) -> dict:
    run_id = _run(root)
    active = run_dir(root, run_id) / "active-item"
    if not active.is_file() or active.read_text(encoding="utf-8").strip() != item_id:
        raise RepairError(f"item {item_id!r} is not the active item")
    active.unlink()
    log = run_dir(root, run_id) / "applied.jsonl"
    with log.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"item": item_id, "at": datetime.datetime.now(datetime.UTC).isoformat()}) + "\n")
    return {"ok": True, "runId": run_id, "finished": item_id}


def cmd_end(root: Path, abandon: bool) -> dict:
    run_id = _run(root)
    rdir = run_dir(root, run_id)
    if not abandon and not (rdir / "verdict.json").is_file():
        raise RepairError("no verdict yet -- run verify.py first, or `end --abandon` to stop without one")
    if (rdir / "active-item").is_file():
        (rdir / "active-item").unlink()
    (repair_dir(root) / "ACTIVE").unlink()
    return {"ok": True, "runId": run_id, "abandoned": abandon}


def cmd_status(root: Path) -> dict:
    run_id = active_run(root)
    if not run_id:
        return {"ok": True, "active": False}
    rdir = run_dir(root, run_id)
    approved = False
    try:
        approved_changeset(root, run_id)
        approved = True
    except RepairError:
        pass
    item = (rdir / "active-item").read_text(encoding="utf-8").strip() if (rdir / "active-item").is_file() else None
    return {
        "ok": True, "active": True, "runId": run_id,
        "preflight": (rdir / "preflight.json").is_file(),
        "objective": (rdir / "objective.json").is_file(),
        "baseline": (rdir / "baseline" / "baseline.json").is_file(),
        "changeset": (rdir / "changeset.json").is_file(),
        "approved": approved, "activeItem": item,
        "verdict": (rdir / "verdict.json").is_file(),
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="repair_state.py", description="Advance a cupertino-repair run through its gates.",
                                     epilog="exit 0 ok, 1 a gate refused, 2 bad usage")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("begin")
    p.add_argument("run_id", nargs="?")
    sub.add_parser("objective")
    sub.add_parser("approve")
    for name in ("start-item", "finish-item"):
        sub.add_parser(name).add_argument("item_id")
    sub.add_parser("end").add_argument("--abandon", action="store_true")
    sub.add_parser("status")
    args = parser.parse_args(argv)
    root = project_root()
    try:
        if args.cmd == "begin":
            out = cmd_begin(root, args.run_id)
        elif args.cmd == "objective":
            out = cmd_objective(root)
        elif args.cmd == "approve":
            out = cmd_approve(root)
        elif args.cmd == "start-item":
            out = cmd_start_item(root, args.item_id)
        elif args.cmd == "finish-item":
            out = cmd_finish_item(root, args.item_id)
        elif args.cmd == "end":
            out = cmd_end(root, args.abandon)
        else:
            out = cmd_status(root)
    except RepairError as err:
        print(json.dumps({"ok": False, "error": str(err)}))
        print(f"repair_state: {err}", file=sys.stderr)
        return 1
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
