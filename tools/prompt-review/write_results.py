#!/usr/bin/env python3
"""Persist a prompt-quality-review workflow return value — or refuse, loudly.

The workflow runs inside the Workflow tool and has no filesystem; the session saves its
return value to a file and hands it here. This script is the only thing that writes
analysis/prompt-review/{run,findings,routing,synthesis}.json, and it writes them only
when the return value is complete and stamped for the args that produced it. Anything
else leaves a FAILED-<stamp> marker and nothing more, so build_report.py cannot render a
stale or partial run as a fresh one (CLAUDE.md: "a failed run leaves the previous output
in place").

Usage: write_results.py <return.json> [--args analysis/prompt-review/args.json]
Exit: 0 written; 1 refused (marker written); 2 bad arguments.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
OUT = ROOT / "analysis/prompt-review"


def write_atomic(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_text(json.dumps(obj, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        os.replace(tmp, path)
    except Exception:
        if tmp.exists():
            tmp.unlink()
        raise


def refuse(reason: str, stamp: str) -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    marker = OUT / f"FAILED-{stamp.replace(':', '')}"
    marker.write_text(f"{dt.datetime.now(dt.timezone.utc).isoformat()}\n{reason}\n", encoding="utf-8")
    print(f"REFUSED: {reason}\nwrote {marker}", file=sys.stderr)
    return 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("ret", type=Path)
    ap.add_argument("--args", type=Path, default=OUT / "args.json")
    a = ap.parse_args(argv)
    if not a.ret.is_file():
        print(f"ERROR: not a file: {a.ret}", file=sys.stderr)
        return 2
    if not a.args.is_file():
        print(f"ERROR: args file missing: {a.args}", file=sys.stderr)
        return 2
    try:
        ret = json.loads(a.ret.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return refuse(f"return value is not JSON: {e}", "unknown")
    args = json.loads(a.args.read_text(encoding="utf-8"))
    stamp = str(ret.get("runStamp") or "unknown")

    if not isinstance(ret, dict) or ret.get("completed") is not True:
        return refuse("return value lacks completed: true", stamp)
    if ret.get("runStamp") != args.get("runStamp"):
        return refuse(f"runStamp {ret.get('runStamp')!r} does not match args {args.get('runStamp')!r}", stamp)
    if ret.get("rubricHash") != args.get("rubricHash"):
        return refuse("rubricHash does not match args", stamp)
    for k in ("findings", "routing", "perPlugin", "calibration", "sealedRecall", "cross"):
        if k not in ret:
            return refuse(f"return value lacks {k}", stamp)
    if not isinstance(ret["findings"], list):
        return refuse("findings is not a list", stamp)

    lint_path = OUT / "lint.json"
    lint = json.loads(lint_path.read_text(encoding="utf-8")) if lint_path.is_file() else {"findings": []}

    run = {
        "runStamp": ret["runStamp"],
        "rubricHash": ret["rubricHash"],
        "writtenAt": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "completed": True,
        "calibration": ret["calibration"],
        "sealedRecall": ret["sealedRecall"],
        "sealedMissed": ret.get("sealedMissed", []),
        "rawCount": ret.get("rawCount"),
        "verifiedCount": ret.get("verifiedCount"),
        "extraFindings": ret.get("extraFindings", 0),
        "batches": ret.get("batches", []),
        "counts": {
            "lint": len(lint.get("findings", [])),
            "verified": len(ret["findings"]),
            "plugins": len(ret["perPlugin"]),
            "collisionPairs": len((ret["routing"] or {}).get("pairs", [])),
            "judged": len((ret["routing"] or {}).get("judged", [])),
        },
    }
    write_atomic(OUT / "findings.json", {"runStamp": ret["runStamp"], "lint": lint.get("findings", []), "verified": ret["findings"]})
    write_atomic(OUT / "routing.json", {"runStamp": ret["runStamp"], **(ret["routing"] or {})})
    write_atomic(OUT / "synthesis.json", {"runStamp": ret["runStamp"], "perPlugin": ret["perPlugin"], "critic": ret.get("critic"), "cross": ret["cross"]})
    write_atomic(OUT / "run.json", run)  # last: its presence means the other three are complete
    print(f"wrote run.json findings.json routing.json synthesis.json for {ret['runStamp']}: "
          f"{run['counts']['verified']} verified + {run['counts']['lint']} lint findings, "
          f"{run['counts']['judged']} judged collisions, sealed recall {ret['sealedRecall']:.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
