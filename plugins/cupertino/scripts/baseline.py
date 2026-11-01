#!/usr/bin/env python3
"""Record what the target is BEFORE any edit: every probe in the objective, and every file's hash.

usage: baseline.py [-h] [--run RUN_ID]

Reads .cupertino/repair/<run>/objective.json (validated first), observes every
acceptance and mustPreserve check into baseline/, hashes every file the objective's
scope covers, and writes baseline/baseline.json. verify.py later repeats exactly the
same observations into after/ and compares.

A baseline is refused once a changeset is approved -- a baseline taken after edits
began would measure the change against itself.

Exit: 0 written; 1 refused (no run, invalid objective, already approved); 2 bad usage.
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import probes  # noqa: E402
from repair_lib import (  # noqa: E402
    RepairError,
    active_run,
    project_root,
    read_json,
    run_dir,
    scope_files,
    sha256_file,
    validate_objective,
    write_json,
)


def all_checks(objective: dict) -> list[tuple[str, str, dict]]:
    """(group, id, check) for every acceptance and mustPreserve criterion."""
    out = [("acceptance", c["id"], c["check"]) for c in objective["acceptance"]]
    out += [("mustPreserve", c["id"], c["check"]) for c in objective.get("mustPreserve", [])]
    return out


def snapshot(root: Path, objective: dict, outdir: Path) -> dict:
    observations = {}
    for group, cid, check in all_checks(objective):
        label = f"{group}-{cid}"
        observations[label] = probes.observe(root, check, outdir, label)
    files = {rel: sha256_file(root / rel) for rel in scope_files(root, objective["scope"])}
    return {"observations": observations, "files": files,
            "at": datetime.datetime.now(datetime.UTC).isoformat()}


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="baseline.py", description="Record probes and file hashes before any edit.",
                                     epilog="exit 0 written, 1 refused, 2 bad usage")
    parser.add_argument("--run", help="run id (default: the active run)")
    args = parser.parse_args(argv)
    root = project_root()
    try:
        run_id = args.run or active_run(root)
        if not run_id:
            raise RepairError("no repair run is active -- run preflight_repair.py first")
        rdir = run_dir(root, run_id)
        if (rdir / "approved").is_file():
            raise RepairError("the changeset is already approved; a baseline now would measure the change against itself")
        objective = read_json(rdir / "objective.json")
        validate_objective(objective)
        snap = snapshot(root, objective, rdir / "baseline")
        snap["objectiveSha256"] = sha256_file(rdir / "objective.json")
        write_json(rdir / "baseline" / "baseline.json", snap)
    except RepairError as err:
        print(f"baseline: {err}", file=sys.stderr)
        return 1
    ran = sum(1 for o in snap["observations"].values() if o.get("ran"))
    print(json.dumps({"ok": True, "runId": run_id, "checks": len(snap["observations"]), "ran": ran,
                      "files": len(snap["files"])}))
    for label, obs in snap["observations"].items():
        if not obs.get("ran"):
            print(f"  not run: {label}: {obs.get('detail')}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
