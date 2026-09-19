#!/usr/bin/env python3
"""Calibration for record_stop_guard.py: it must block AND allow.

usage: python3 plugins/arbeitsplan/hooks/test_record_stop_guard.py

Every case runs the hook as a subprocess, exactly as the harness does. A hook
whose only tested path is the block is a hook nobody checked for trapping a
session, so the allow cases carry equal weight.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import run_record  # vendored copy of tools/run-record/run_record.py

HOOK = Path(__file__).resolve().parent / "record_stop_guard.py"

FAILS: list = []


def run(cwd: Path, active: bool = False, env: dict | None = None) -> tuple:
    p = subprocess.run([sys.executable, str(HOOK)],
                       input=json.dumps({"hook_event_name": "Stop", "cwd": str(cwd), "stop_hook_active": active}),
                       capture_output=True, text=True, env={"PATH": "/usr/bin:/bin", **(env or {})})
    return p.returncode, p.stdout, p.stderr


def check(name: str, cond: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if cond else 'FAIL'} {name}")
    if not cond:
        FAILS.append(name)
        if detail:
            print(f"       {detail[:200]}")


def main() -> int:
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        rc, out, _ = run(tmp)
        check("no lock -> ALLOW (inert)", rc == 0 and not out.strip())

        lock = tmp / "analysis" / "arbeitsplan" / "run_scope.json"
        lock.parent.mkdir(parents=True)
        lock.write_text(json.dumps({"runId": "ap-s-1", "phase": "build"}))
        rc, out, err = run(tmp)
        check("lock but no run.jsonl -> BLOCK", rc == 2 and "no run.jsonl" in err, err)

        run_ = run_record.open_run("arbeitsplan", "ap-s-1", tmp)
        run_.append({"trace_id": "ap-s-1", "span_id": "s1", "parent_span_id": "r", "span": "phase build",
                     "node_id": "build", "status": "opened"})
        rc, out, err = run(tmp)
        check("open phase -> BLOCK", rc == 2, err)
        check("  ...with decision:block JSON on stdout", json.loads(out or "{}").get("decision") == "block", out)
        check("  ...naming both legal moves", "--status closed" in err and "--halt" in err, err)

        rc, _, _ = run(tmp, active=True)
        check("stop_hook_active -> ALLOW (blocks at most once)", rc == 0)
        rc, _, _ = run(tmp, env={"ARBEITSPLAN_DISABLE_GUARD": "1"})
        check("escape hatch -> ALLOW", rc == 0)

        run_.halt("CONTRACT PROBLEM: 1/3 usable", "build")
        rc, _, err = run(tmp)
        check("phase recorded halted -> ALLOW", rc == 0, err)

        lock.write_text(json.dumps({"runId": "ap-s-1", "phase": "land"}))
        run_.append({"trace_id": "ap-s-1", "span_id": "s2", "parent_span_id": "r", "span": "phase land",
                     "node_id": "land", "status": "closed"})
        rc, _, err = run(tmp)
        check("phase recorded closed -> ALLOW", rc == 0, err)

        # Below the floor, against a REAL old interpreter when this machine has one
        # (stock macOS /usr/bin/python3 is 3.9) -- never a simulated version.
        old = Path("/usr/bin/python3")
        vers = subprocess.run([str(old), "-c", "import sys; print(sys.version_info[:2] < (3, 11))"],
                              capture_output=True, text=True).stdout.strip() if old.is_file() else ""
        if vers == "True":
            p = subprocess.run([str(old), str(HOOK)], capture_output=True, text=True,
                               input=json.dumps({"cwd": str(tmp), "stop_hook_active": False}))
            check("below the Python floor -> BLOCK naming the version", p.returncode == 2 and "3.11" in p.stderr, p.stderr)
        else:
            print("  skip below-the-floor case: no python3 older than 3.11 on this machine")

        (run_.log).write_text("{not json\n")
        rc, _, err = run(tmp)
        check("damaged record -> BLOCK, naming the escape hatch", rc == 2 and "ARBEITSPLAN_DISABLE_GUARD" in err, err)
    print()
    if FAILS:
        print(f"FAILED ({len(FAILS)}): {', '.join(FAILS)}")
        return 1
    print("all record_stop_guard cases passed (blocks AND allows)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
