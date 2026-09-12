#!/usr/bin/env python3
"""Calibration for arbeitsplan_guard.py -- it must DENY and it must ALLOW.

A guard that denies everything is as broken as one that denies nothing, and
only the first kind gets noticed. Every rule is asserted in both directions.

The negative cases carry the weight here, because this guard's design claim is
narrow on purpose: it polices per-dispatch attribution and nothing else.
Ordering belongs to takt. If a case below starts passing because this guard
grew an opinion about order, the two plugins now disagree about one question
and that is a defect, not extra safety.

Groups, named so a sabotage run can be read at a glance:

  WIDEN     two different candidates in one phase must BOTH proceed. If this
            goes red the guard has broken the only convergence mechanism the
            plugin has.
  REPEAT    a byte-identical re-dispatch must be denied.
  SCOPE     writes outside the declared scope, and shared-tree writes during a
            fan-out, must be denied.
  BUDGET    dispatches past the declared ceiling must be denied.

Sabotage checks (run them, do not assume them):
  * make dispatch_signature() return a constant -> WIDEN goes red.
  * swap os.O_EXCL out of the os.open() flags  -> REPEAT goes red.
  * make matches() return True unconditionally -> SCOPE goes red.

Run: python3 plugins/arbeitsplan/hooks/test_arbeitsplan_guard.py
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

GUARD = Path(__file__).resolve().parent / "arbeitsplan_guard.py"

DENY = 2
ALLOW = 0

FAILURES: list = []


def run(cwd: Path, tool: str, tool_input: dict, env: dict | None = None) -> tuple:
    event = json.dumps({"cwd": str(cwd), "tool_name": tool, "tool_input": tool_input})
    proc = subprocess.run(
        [sys.executable, str(GUARD)],
        input=event,
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin", **(env or {})},
    )
    return proc.returncode, (proc.stdout + proc.stderr)


def lock(tmp: Path, **over) -> None:
    body = {
        "runId": "ap-test-1",
        "phase": "build",
        "kind": "fanout-redundant",
        "sharedTreeWritable": False,
        "writeScope": ["src/api/**", "tests/test_api.py"],
        "candidates": [
            {"id": "c1", "worktree": str(tmp / ".arbeitsplan" / "c1")},
            {"id": "c2", "worktree": str(tmp / ".arbeitsplan" / "c2")},
        ],
        "fanOut": 2,
        "budget": {"totalDispatches": 4},
    }
    body.update(over)
    path = tmp / "analysis" / "arbeitsplan"
    path.mkdir(parents=True, exist_ok=True)
    (path / "run_scope.json").write_text(json.dumps(body, indent=2))


def reset_ledger(tmp: Path, run_id: str = "ap-test-1") -> None:
    import shutil

    d = tmp / "analysis" / "arbeitsplan" / run_id / "dispatch"
    if d.exists():
        shutil.rmtree(d)


def check(name: str, got: int, want: int, out: str = "") -> None:
    if got == want:
        print(f"  ok   {name}")
    else:
        names = {DENY: "DENY", ALLOW: "ALLOW"}
        print(f"  FAIL {name}: wanted {names.get(want, want)}, got {names.get(got, got)}")
        if out:
            print(f"       {next(iter(out.strip().splitlines()), '')}")
        FAILURES.append(name)


def main() -> int:
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)

        print("inertness")
        rc, _ = run(tmp, "Edit", {"file_path": "anything.py"})
        check("no run_scope.json -> ALLOW", rc, ALLOW)
        rc, _ = run(tmp, "Agent", {"prompt": "go"})
        check("no run in flight, dispatch -> ALLOW", rc, ALLOW)

        lock(tmp)
        rc, _ = run(tmp, "Edit", {"file_path": "src/api/x.py"},
                    {"ARBEITSPLAN_DISABLE_GUARD": "1"})
        check("escape hatch -> ALLOW", rc, ALLOW)
        rc, _ = run(tmp, "Read", {"file_path": "/etc/passwd"})
        check("tool outside the matcher -> ALLOW", rc, ALLOW)

        print("WIDEN (different candidates must both proceed)")
        reset_ledger(tmp)
        rc, _ = run(tmp, "Agent", {"prompt": "angle: middleware"})
        check("candidate 1 -> ALLOW", rc, ALLOW)
        rc, _ = run(tmp, "Agent", {"prompt": "angle: decorator"})
        check("candidate 2, different angle -> ALLOW", rc, ALLOW)
        rc, _ = run(tmp, "Agent", {"prompt": "angle: proxy"})
        check("candidate 3, different angle -> ALLOW", rc, ALLOW)

        print("REPEAT (identical re-dispatch is the serial loop)")
        rc, out = run(tmp, "Agent", {"prompt": "angle: middleware"})
        check("byte-identical re-dispatch -> DENY", rc, DENY, out)
        if rc == DENY and "WIDENING" not in out:
            FAILURES.append("repeat denial explains widening")
            print("  FAIL repeat denial explains widening")

        print("BUDGET (ceiling is declared, not negotiated)")
        rc, out = run(tmp, "Agent", {"prompt": "angle: fourth"})
        check("4th distinct dispatch fills budget -> ALLOW", rc, ALLOW, out)
        rc, out = run(tmp, "Agent", {"prompt": "angle: fifth"})
        check("5th distinct dispatch past budget -> DENY", rc, DENY, out)

        print("SCOPE (writes during a fan-out phase)")
        reset_ledger(tmp)
        c1 = tmp / ".arbeitsplan" / "c1"
        c1.mkdir(parents=True, exist_ok=True)

        rc, out = run(tmp, "Edit", {"file_path": "src/api/x.py"})
        check("shared-tree write during fan-out -> DENY", rc, DENY, out)

        rc, _ = run(tmp, "Edit", {"file_path": str(c1 / "src" / "api" / "x.py")})
        check("in-worktree write inside scope -> ALLOW", rc, ALLOW)

        # A symlink is the way a lexically-contained path reaches outside the
        # worktree. The containment check was purely lexical, so this write
        # looked in-scope and landed on the shared tree.
        outside = tmp / "outside"
        outside.mkdir(parents=True, exist_ok=True)
        (c1 / "src" / "api").mkdir(parents=True, exist_ok=True)
        link = c1 / "src" / "api" / "escape.py"
        if link.is_symlink() or link.exists():
            link.unlink()
        link.symlink_to(outside / "escape.py")
        rc, out = run(tmp, "Edit", {"file_path": str(link)})
        check("in-worktree SYMLINK pointing outside -> DENY", rc, DENY, out)

        rc, out = run(tmp, "Edit", {"file_path": str(c1 / "src" / "secrets.py")})
        check("in-worktree write OUTSIDE scope -> DENY", rc, DENY, out)

        rc, out = run(tmp, "MultiEdit", {"edits": [
            {"file_path": str(c1 / "src" / "api" / "a.py")},
            {"file_path": str(c1 / "docs" / "leak.md")},
        ]})
        check("MultiEdit, any path out of scope -> DENY", rc, DENY, out)

        rc, out = run(tmp, "Edit", {"edits": "notalist"})
        check("no determinable path -> DENY (fail-closed)", rc, DENY, out)

        print("SCOPE (single-writer phase may touch the shared tree)")
        lock(tmp, phase="land", kind="single-writer", sharedTreeWritable=True)
        rc, _ = run(tmp, "Edit", {"file_path": "src/api/x.py"})
        check("landing phase, in scope -> ALLOW", rc, ALLOW)
        rc, out = run(tmp, "Edit", {"file_path": "src/secrets.py"})
        check("landing phase, out of scope -> DENY", rc, DENY, out)

        print("fail-closed on a malformed lock")
        for bad in ({"writeScope": []}, {"budget": {}}, {"runId": ""}):
            lock(tmp, **bad)
            rc, out = run(tmp, "Edit", {"file_path": "src/api/x.py"})
            key = next(iter(bad))
            if key == "budget":
                rc, out = run(tmp, "Agent", {"prompt": "x"})
            check(f"malformed lock ({key}) -> DENY", rc, DENY, out)

        print("DELEGATION (cross-plugin only; own agents are fan-out, not depth)")
        # Its own budget: the earlier groups deliberately exhaust theirs, and a
        # budget denial fires BEFORE the delegation check -- which is correct
        # ordering, but it would mask every case below.
        lock(tmp, budget={"totalDispatches": 40})
        reset_ledger(tmp)
        led = tmp / "analysis" / "arbeitsplan" / "ap-test-1" / "delegation.jsonl"
        if led.exists():
            led.unlink()

        rc, _ = run(tmp, "Agent", {"subagent_type": "arbeitsplan:candidate-builder",
                                   "prompt": "own agent, angle one"})
        check("own-plugin agent -> ALLOW", rc, ALLOW)
        wrote = led.exists()
        check("own-plugin agent writes NO delegation record",
              ALLOW if not wrote else DENY, ALLOW)

        rc, _ = run(tmp, "Agent", {"subagent_type": "compass:compass-explore-branches",
                                   "prompt": "delegate out"})
        check("cross-plugin delegation at depth 0 -> ALLOW", rc, ALLOW)
        recs = [json.loads(x) for x in led.read_text().splitlines() if x.strip()] if led.exists() else []
        check("cross-plugin delegation IS recorded",
              ALLOW if len(recs) == 1 and recs[0]["target"] == "compass:compass-explore-branches" else DENY,
              ALLOW)

        print("DEPTH (cap at 3)")
        # Build a chain by hand, then point the lock at its tip.
        chain = [
            {"id": "d1", "runId": "ap-test-1", "parent": None, "depth": 0,
             "source": "arbeitsplan", "target": "compass", "pattern": "serial",
             "chain": ["arbeitsplan", "compass"], "merge": None,
             "status": "completed", "timestamp": "2026-09-12T09:00:00Z"},
            {"id": "d2", "runId": "ap-test-1", "parent": "d1", "depth": 1,
             "source": "compass", "target": "andon", "pattern": "serial",
             "chain": ["compass", "andon"], "merge": None,
             "status": "completed", "timestamp": "2026-09-12T09:01:00Z"},
            {"id": "d3", "runId": "ap-test-1", "parent": "d2", "depth": 2,
             "source": "andon", "target": "lehre", "pattern": "serial",
             "chain": ["andon", "lehre"], "merge": None,
             "status": "completed", "timestamp": "2026-09-12T09:02:00Z"},
        ]
        led.parent.mkdir(parents=True, exist_ok=True)
        led.write_text("".join(json.dumps(r) + "\n" for r in chain))

        lock(tmp, budget={"totalDispatches": 40}, delegationParent="d2", delegationSource="andon")
        rc, out = run(tmp, "Agent", {"subagent_type": "matrize:matrize-decode", "prompt": "x"})
        check("depth 2 -> ALLOW (one level left)", rc, ALLOW, out)

        lock(tmp, budget={"totalDispatches": 40}, delegationParent="d3", delegationSource="lehre")
        rc, out = run(tmp, "Agent", {"subagent_type": "matrize:matrize-name", "prompt": "y"})
        check("depth 3 -> DENY (cap)", rc, DENY, out)
        if rc == DENY and "depth" not in out.lower():
            FAILURES.append("depth denial names the cap")
            print("  FAIL depth denial names the cap")

        print("CYCLE (caught below the cap, not by it)")
        lock(tmp, budget={"totalDispatches": 40}, delegationParent="d1", delegationSource="compass")
        rc, out = run(tmp, "Agent", {"subagent_type": "arbeitsplan:x", "prompt": "back to start"})
        check("A->B->A cycle back to the run owner -> DENY", rc, DENY, out)

        lock(tmp, budget={"totalDispatches": 40}, delegationParent="d2", delegationSource="andon")
        rc, out = run(tmp, "Agent", {"subagent_type": "compass:anything", "prompt": "cycle"})
        check("A->B->C->B cycle -> DENY", rc, DENY, out)
        if rc == DENY and "cycle" not in out.lower():
            FAILURES.append("cycle denial says cycle")
            print("  FAIL cycle denial says cycle")

        print("deny protocol")
        lock(tmp)
        reset_ledger(tmp)
        payload = json.dumps({"cwd": str(tmp), "tool_name": "Edit",
                              "tool_input": {"file_path": "src/api/x.py"}})
        proc = subprocess.run([sys.executable, str(GUARD)], input=payload,
                              capture_output=True, text=True,
                              env={"PATH": "/usr/bin:/bin"})
        ok = proc.returncode == DENY and bool(proc.stderr.strip())
        try:
            out_payload = json.loads(proc.stdout)["hookSpecificOutput"]
        except Exception:
            out_payload = {}
        if out_payload.get("hookEventName") != "PreToolUse":
            ok = False
        if out_payload.get("permissionDecision") != "deny":
            ok = False
        if not out_payload.get("permissionDecisionReason"):
            ok = False
        check("exit 2 + stdout JSON (hookEventName/decision/reason) + stderr",
              ALLOW if ok else DENY, ALLOW)
        if "ARBEITSPLAN_DISABLE_GUARD" not in (proc.stdout + proc.stderr):
            FAILURES.append("deny names the escape hatch")
            print("  FAIL deny names the escape hatch")

    print()
    if FAILURES:
        print(f"FAILED ({len(FAILURES)}): " + ", ".join(FAILURES))
        return 1
    print("all arbeitsplan guard cases passed (denies AND allows)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
