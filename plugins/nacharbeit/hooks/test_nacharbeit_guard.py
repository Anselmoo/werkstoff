#!/usr/bin/env python3
"""Behavioural tests for nacharbeit_guard: does it actually DENY, and actually ALLOW.

    python3 plugins/nacharbeit/hooks/test_nacharbeit_guard.py

"The hook exists" and "the hook fires" are different claims, and this repo has
shipped the first while believing the second. Every case here builds a real
temporary repository, feeds a real PreToolUse payload on stdin, and asserts on
the process exit code AND on the stdout JSON shape the runtime requires -- a
deny that omits hookSpecificOutput.hookEventName is discarded by the runtime,
so a guard can deny correctly and still be ignored.

Usage: test_nacharbeit_guard.py
Exit: 0 every case passed; 1 any case failed.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile

GUARD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nacharbeit_guard.py")
FAILS: list[str] = []
LOCK = {
    "runStamp": "2026-09-09T00:00:00Z",
    "createdAt": "2026-09-09T00:00:00Z",
    "reviewRunStamp": "2026-09-08T00:00:00Z",
    "stateDir": "analysis/nacharbeit",
    "writeRoots": ["plugins/"],
    "files": {
        "plugins/demo/skills/one/SKILL.md": "haiku",
        "plugins/demo/agents/two.md": "sonnet",
        "plugins/demo/skills/three/SKILL.md": "opus",
        "plugins/demo/README.md": "human",
    },
}


def run(cwd, payload, env_extra=None):
    env = dict(os.environ)
    env.pop("NACHARBEIT_DISABLE_GUARD", None)
    env.pop("NACHARBEIT_STATE_DIR", None)
    if env_extra:
        env.update(env_extra)
    return subprocess.run([sys.executable, GUARD], input=json.dumps(payload),
                          capture_output=True, text=True, cwd=cwd, env=env, timeout=30)


def make_repo(with_lock=True, lock=LOCK):
    root = tempfile.mkdtemp(prefix="nacharbeit-test-")
    os.makedirs(os.path.join(root, "plugins", "demo", "skills", "one"), exist_ok=True)
    if with_lock:
        os.makedirs(os.path.join(root, "analysis", "nacharbeit"), exist_ok=True)
        with open(os.path.join(root, "analysis", "nacharbeit", "fix_scope.json"), "w", encoding="utf-8") as fh:
            fh.write(lock if isinstance(lock, str) else json.dumps(lock))
    return root


def expect_deny(label, proc, must_mention=None):
    if proc.returncode != 2:
        FAILS.append(f"{label}: expected exit 2, got {proc.returncode}. stderr={proc.stderr[:200]!r}")
        return
    try:
        out = json.loads(proc.stdout)
    except json.JSONDecodeError:
        FAILS.append(f"{label}: stdout is not JSON: {proc.stdout[:200]!r}")
        return
    hso = out.get("hookSpecificOutput", {})
    if hso.get("hookEventName") != "PreToolUse" or hso.get("permissionDecision") != "deny" or not hso.get("permissionDecisionReason"):
        FAILS.append(f"{label}: deny JSON lacks the required hookSpecificOutput shape: {out}")
        return
    if must_mention and must_mention not in hso["permissionDecisionReason"]:
        FAILS.append(f"{label}: reason does not mention {must_mention!r}: {hso['permissionDecisionReason']}")


def expect_allow(label, proc):
    if proc.returncode != 0:
        FAILS.append(f"{label}: expected exit 0, got {proc.returncode}. stderr={proc.stderr[:200]!r}")


def edit(path, tool="Edit"):
    return {"tool_name": tool, "tool_input": {"file_path": path, "old_string": "a", "new_string": "b"}}


def main() -> int:
    repos = []
    try:
        # inert: no lock
        r = make_repo(with_lock=False)
        repos.append(r)
        expect_allow("no lock allows any edit", run(r, {"cwd": r, **edit("plugins/demo/agents/two.md")}))
        expect_allow("no lock allows git commit", run(r, {"cwd": r, "tool_name": "Bash", "tool_input": {"command": "git commit -m x"}}))

        r = make_repo()
        repos.append(r)
        expect_allow("in-lock haiku file allowed", run(r, {"cwd": r, **edit("plugins/demo/skills/one/SKILL.md")}))
        expect_allow("in-lock sonnet file allowed (absolute path)", run(r, {"cwd": r, **edit(os.path.join(r, "plugins/demo/agents/two.md"))}))
        expect_deny("file not in lock denied", run(r, {"cwd": r, **edit("plugins/demo/agents/other.md")}), "not in the fix scope")
        expect_deny("opus-tier file denied", run(r, {"cwd": r, **edit("plugins/demo/skills/three/SKILL.md")}), "opus-tier")
        expect_deny("human-tier file denied", run(r, {"cwd": r, **edit("plugins/demo/README.md", tool="Write")}), "human-tier")
        expect_deny("MultiEdit with one out-of-lock path denied", run(r, {"cwd": r, "tool_name": "MultiEdit", "tool_input": {
            "edits": [{"file_path": "plugins/demo/skills/one/SKILL.md"}, {"file_path": "plugins/demo/agents/other.md"}]}}), "not in the fix scope")
        expect_allow("MultiEdit with all in-lock paths allowed", run(r, {"cwd": r, "tool_name": "MultiEdit", "tool_input": {
            "edits": [{"file_path": "plugins/demo/skills/one/SKILL.md"}, {"file_path": "plugins/demo/agents/two.md"}]}}))
        expect_deny("file_paths list with out-of-lock path denied", run(r, {"cwd": r, "tool_name": "Write", "tool_input": {
            "file_paths": ["plugins/demo/agents/two.md", "plugins/demo/x.md"]}}), "not in the fix scope")
        expect_deny("file_paths as a string is an empty set, denied", run(r, {"cwd": r, "tool_name": "Write", "tool_input": {
            "file_paths": "plugins/demo/agents/two.md"}}), "no determinable file path")
        expect_deny("empty target set denied", run(r, {"cwd": r, "tool_name": "Edit", "tool_input": {}}), "no determinable file path")
        expect_allow("write into the state dir allowed", run(r, {"cwd": r, **edit("analysis/nacharbeit/return.json", tool="Write")}))
        expect_allow("git status allowed", run(r, {"cwd": r, "tool_name": "Bash", "tool_input": {"command": "git status --short"}}))
        expect_allow("git diff allowed", run(r, {"cwd": r, "tool_name": "Bash", "tool_input": {"command": "git diff -- plugins/demo"}}))
        expect_deny("git commit denied", run(r, {"cwd": r, "tool_name": "Bash", "tool_input": {"command": "git commit -m 'fix'"}}), "git commit")
        expect_deny("chained git push denied", run(r, {"cwd": r, "tool_name": "Bash", "tool_input": {"command": "python3 x.py && git push -u origin main"}}), "git push")
        expect_deny("gh pr create denied", run(r, {"cwd": r, "tool_name": "Bash", "tool_input": {"command": "gh pr create --fill"}}), "gh pr create")
        expect_allow("plain python allowed", run(r, {"cwd": r, "tool_name": "Bash", "tool_input": {"command": "python3 -m py_compile plugins/demo/x.py"}}))
        expect_allow("unrelated tool allowed", run(r, {"cwd": r, "tool_name": "Read", "tool_input": {"file_path": "plugins/demo/README.md"}}))
        expect_allow("escape hatch allows an out-of-lock edit", run(r, {"cwd": r, **edit("plugins/demo/agents/other.md")}, {"NACHARBEIT_DISABLE_GUARD": "1"}))
        expect_allow("unparseable stdin is allowed", subprocess.run([sys.executable, GUARD], input="not json", capture_output=True, text=True, cwd=r, timeout=30))

        r = make_repo(lock="{not json")
        repos.append(r)
        expect_deny("malformed lock denies (fail closed)", run(r, {"cwd": r, **edit("plugins/demo/skills/one/SKILL.md")}), "NACHARBEIT_DISABLE_GUARD")
        r = make_repo(lock={"runStamp": "x"})
        repos.append(r)
        expect_deny("lock without files map denies", run(r, {"cwd": r, **edit("plugins/demo/skills/one/SKILL.md")}), "no `files` map")

        # relocated state dir
        r = make_repo(with_lock=False)
        repos.append(r)
        os.makedirs(os.path.join(r, "state"), exist_ok=True)
        with open(os.path.join(r, "state", "fix_scope.json"), "w", encoding="utf-8") as fh:
            json.dump(LOCK, fh)
        expect_deny("NACHARBEIT_STATE_DIR relocates the lock", run(r, {"cwd": r, **edit("plugins/demo/agents/other.md")}, {"NACHARBEIT_STATE_DIR": "state"}), "not in the fix scope")

        # heartbeat (#117): the only proof the runtime actually registered this hook
        def beat(root):
            path = os.path.join(root, "analysis", "nacharbeit", "guard-heartbeat.json")
            if not os.path.isfile(path):
                return None
            with open(path, "r", encoding="utf-8") as fh:
                return json.load(fh)

        def rm_beat(root):
            try:
                os.remove(os.path.join(root, "analysis", "nacharbeit", "guard-heartbeat.json"))
            except FileNotFoundError:
                pass  # absent is what the following assertion reports; do not crash the run

        r = make_repo(with_lock=False)
        repos.append(r)
        run(r, {"cwd": r, **edit("plugins/demo/agents/two.md")})
        if os.path.exists(os.path.join(r, "analysis")):
            FAILS.append("no lock: the guard wrote into the repository although it must stay inert")
        r = make_repo()
        repos.append(r)
        expect_allow("heartbeat repo: allowed edit", run(r, {"cwd": r, **edit("plugins/demo/skills/one/SKILL.md")}))
        hb = beat(r)
        if not hb or hb.get("lockRunStamp") != LOCK["runStamp"] or hb.get("tool") != "Edit" or not hb.get("seenAt"):
            FAILS.append(f"allowed call under a lock did not write a heartbeat bound to the lock's runStamp: {hb}")
        rm_beat(r)
        expect_deny("heartbeat repo: denied edit", run(r, {"cwd": r, **edit("plugins/demo/agents/other.md", tool="Write")}), "not in the fix scope")
        hb = beat(r)
        if not hb or hb.get("tool") != "Write":
            FAILS.append(f"a DENIED call under a lock must also write a heartbeat (the guard fired): {hb}")
        rm_beat(r)
        run(r, {"cwd": r, **edit("plugins/demo/agents/other.md")}, {"NACHARBEIT_DISABLE_GUARD": "1"})
        if beat(r) is not None:
            FAILS.append("NACHARBEIT_DISABLE_GUARD=1 wrote a heartbeat: a disabled guard would confirm itself")
        # an unwritable heartbeat must not change a single decision
        os.makedirs(os.path.join(r, "analysis", "nacharbeit", "guard-heartbeat.json"))
        expect_deny("unwritable heartbeat still denies", run(r, {"cwd": r, **edit("plugins/demo/agents/other.md")}), "not in the fix scope")
        expect_allow("unwritable heartbeat still allows", run(r, {"cwd": r, **edit("plugins/demo/skills/one/SKILL.md")}))
    finally:
        for r in repos:
            shutil.rmtree(r, ignore_errors=True)

    for f in FAILS:
        print(f"FAIL {f}")
    print(f"{'GREEN' if not FAILS else 'RED'}: {len(FAILS)} failure(s)")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
