#!/usr/bin/env python3
"""The cupertino-repair rules in pretooluse_guard.py: every rule denies AND allows.

Builds a throwaway repo, drives a real repair run with the plugin's own scripts
(preflight -> objective -> baseline -> changeset -> approve -> start-item), and
feeds the real hook the payloads a session would send at each gate. A rule that
is only ever shown denying could be denying everything; each one here is paired
with the closest call it must allow.

Usage: python3 plugins/cupertino/hooks/test_repair_guard.py   (exit 0 all pass, 1 any fail)
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HOOKS = Path(__file__).resolve().parent
PLUGIN = HOOKS.parent
GUARD = HOOKS / "pretooluse_guard.py"
SCRIPTS = PLUGIN / "scripts"
ALLOW, DENY = 0, 2
failures = 0


def hook(root: Path, tool: str, tool_input: dict) -> subprocess.CompletedProcess:
    payload = {"cwd": str(root), "tool_name": tool, "tool_input": tool_input, "hook_event_name": "PreToolUse"}
    env = {k: v for k, v in os.environ.items() if k not in ("CUPERTINO_DISABLE_GUARD", "CLAUDE_PROJECT_DIR")}
    env["CLAUDE_PLUGIN_ROOT"] = str(PLUGIN)
    return subprocess.run([sys.executable, "-B", str(GUARD)], input=json.dumps(payload), capture_output=True,
                          text=True, env=env, check=False)


def expect(name: str, root: Path, tool: str, tool_input: dict, want: int, must_say: str = "") -> None:
    global failures
    p = hook(root, tool, tool_input)
    ok = p.returncode == want and (not must_say or must_say in p.stderr)
    if want == DENY and ok:
        try:
            out = json.loads(p.stdout)["hookSpecificOutput"]
            ok = out["hookEventName"] == "PreToolUse" and out["permissionDecision"] == "deny"
        except (ValueError, KeyError):
            ok = False
    failures += not ok
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + ("" if ok else f" (exit {p.returncode}, want {want}): {p.stderr.strip()[-300:]}"))


def script(root: Path, name: str, *args: str) -> None:
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(root))
    p = subprocess.run([sys.executable, str(SCRIPTS / name), *args], cwd=root, env=env, capture_output=True, text=True, check=False)
    if p.returncode != 0:
        raise SystemExit(f"setup step {name} {args} failed: {p.stderr or p.stdout}")


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "app").mkdir()
        (root / "app" / "styles.css").write_text(".kpis { display: flex; }\n", encoding="utf-8")
        (root / "app" / "chart.js").write_text("const PALETTE = { bar: '#1874c2' };\n", encoding="utf-8")
        (root / "app" / "legacy.js").write_text("function old() {}\n", encoding="utf-8")
        (root / "README.md").write_text("# app\n", encoding="utf-8")

        print("no .cupertino/ yet (first use)")
        expect("a gated skill is denied on first use, naming backwards and repair", root, "Skill",
               {"skill": "cupertino:cupertino-council"}, DENY, "cupertino-repair")
        expect("an ungated skill is allowed on first use", root, "Skill", {"skill": "cupertino:cupertino-backwards"}, ALLOW)
        expect("an unrelated edit is allowed (still inert for everything else)", root, "Edit",
               {"file_path": str(root / "app" / "chart.js")}, ALLOW)

        script(root, "preflight_repair.py", "--target", "app", "--run-id", "t1")
        rdir = root / ".cupertino" / "repair" / "t1"
        print("run begun, no objective or baseline")
        expect("a source edit before the objective is denied", root, "Edit", {"file_path": "app/styles.css"}, DENY, "objective.json")
        expect("writing the objective itself is allowed", root, "Write",
               {"file_path": str(rdir / "objective.json"), "content": "{}"}, ALLOW)
        expect("forging preflight.json is denied", root, "Write", {"file_path": str(rdir / "preflight.json"), "content": "{}"},
               DENY, "written only by the repair scripts")
        expect("forging a baseline file is denied", root, "Write",
               {"file_path": str(rdir / "baseline" / "baseline.json"), "content": "{}"}, DENY, "written only by the repair scripts")
        expect("forging verdict.json is denied", root, "Write", {"file_path": str(rdir / "verdict.json"), "content": "{}"},
               DENY, "written only by the repair scripts")

        (rdir / "objective.json").write_text(json.dumps({
            "objective": "the KPI row must wrap on small screens and legacy.js must go",
            "scope": ["app/**"],
            "acceptance": [{"id": "A1", "criterion": "legacy gone", "check": {"kind": "file", "path": "app/legacy.js", "exists": False}}],
            "mustPreserve": [{"id": "P1", "criterion": "chart untouched", "check": {"kind": "file", "path": "app/chart.js", "unchanged": True}}],
        }), encoding="utf-8")
        script(root, "baseline.py")
        (rdir / "changeset.json").write_text(json.dumps({"items": [
            {"id": "I1", "op": "modify", "paths": ["app/styles.css"], "rationale": "wrap"},
            {"id": "I2", "op": "delete", "paths": ["app/legacy.js"], "rationale": "dead", "evidence": "nothing imports it"},
            {"id": "I3", "op": "create", "paths": ["app/new.css"], "rationale": "split"},
        ]}), encoding="utf-8")
        print("objective + baseline + changeset, not approved")
        expect("an edit before approval is denied", root, "Edit", {"file_path": "app/styles.css"}, DENY, "not been approved")

        script(root, "repair_state.py", "approve")
        print("approved, no active item")
        expect("an edit with no active item is denied", root, "Edit", {"file_path": "app/styles.css"}, DENY, "no item is active")

        script(root, "repair_state.py", "start-item", "I1")
        print("item I1 (modify app/styles.css) active")
        expect("Edit of the active item's path is allowed", root, "Edit", {"file_path": "app/styles.css"}, ALLOW)
        expect("an absolute path to the same file is allowed", root, "Edit", {"file_path": str(root / "app" / "styles.css")}, ALLOW)
        expect("MultiEdit of the active item's path is allowed", root, "MultiEdit", {"file_path": "app/styles.css", "edits": []}, ALLOW)
        expect("Edit of a file no item names is denied", root, "Edit", {"file_path": "app/chart.js"}, DENY, "not in active item")
        expect("MultiEdit outside scope is denied (MultiEdit was unmatched before)", root, "MultiEdit",
               {"file_path": "app/chart.js", "edits": []}, DENY, "not in active item")
        expect("edits[].file_path outside the item is denied", root, "MultiEdit",
               {"edits": [{"file_path": "app/chart.js", "old_string": "a", "new_string": "b"}]}, DENY, "not in active item")
        expect("file_paths outside the item is denied", root, "Edit", {"file_paths": ["app/styles.css", "app/chart.js"]},
               DENY, "not in active item")
        expect("an edit naming no readable path is denied during a run", root, "Edit", {"file_path": 7}, DENY, "names no path")
        expect("a ../ escape is denied", root, "Write", {"file_path": "../outside.txt", "content": "x"}, DENY, "outside the project")
        expect("changing the changeset mid-item is denied", root, "Write",
               {"file_path": str(rdir / "changeset.json"), "content": "{}"}, DENY, "finish-item")
        expect("bash rm is denied", root, "Bash", {"command": "rm app/legacy.js"}, DENY, "apply_delete.py")
        expect("bash sed -i is denied", root, "Bash", {"command": "sed -i 's/flex/grid/' app/styles.css"}, DENY)
        expect("bash redirect into a file is denied", root, "Bash", {"command": "echo x > app/chart.js"}, DENY)
        expect("git commit during a run is denied", root, "Bash", {"command": "git commit -am wip"}, DENY)
        expect("a read-only bash command is allowed", root, "Bash", {"command": "grep -rn kpis app/ 2>/dev/null"}, ALLOW)
        expect("running the plugin's own scripts is allowed", root, "Bash",
               {"command": f"python3 {SCRIPTS}/apply_delete.py --item I2"}, ALLOW)
        expect("a building skill is denied during a run", root, "Skill", {"skill": "cupertino:cupertino-reveal"}, DENY, "repair run is active")

        script(root, "repair_state.py", "finish-item", "I1")
        script(root, "repair_state.py", "start-item", "I2")
        print("item I2 (delete) active")
        expect("editing a delete item's path is denied, naming the script", root, "Edit", {"file_path": "app/legacy.js"},
               DENY, "apply_delete.py")

        script(root, "repair_state.py", "finish-item", "I2")
        script(root, "repair_state.py", "start-item", "I3")
        print("item I3 (create app/new.css) active")
        expect("Write of the file a create item names is allowed", root, "Write", {"file_path": "app/new.css", "content": "a{}"}, ALLOW)
        (root / "app" / "new.css").write_text("a{}", encoding="utf-8")
        expect("a create over an existing file is denied", root, "Write", {"file_path": "app/new.css", "content": "b{}"},
               DENY, "already exists")

        script(root, "repair_state.py", "finish-item", "I3")
        (rdir / "changeset.json").write_text(json.dumps({"items": [
            {"id": "I1", "op": "modify", "paths": ["app/styles.css", "app/chart.js"], "rationale": "sneak"}]}), encoding="utf-8")
        print("changeset edited after approval")
        script_env = dict(os.environ, CLAUDE_PROJECT_DIR=str(root))
        p = subprocess.run([sys.executable, str(SCRIPTS / "repair_state.py"), "start-item", "I1"], cwd=root, env=script_env,
                           capture_output=True, text=True, check=False)
        ok = p.returncode == 1 and "changed after approval" in p.stderr
        global failures
        failures += not ok
        print(f"  {'ok  ' if ok else 'FAIL'} start-item refuses a changeset edited after approval")
        (rdir / "active-item").write_text("I1\n", encoding="utf-8")
        expect("the guard refuses it too, even with an active-item file planted", root, "Edit", {"file_path": "app/chart.js"},
               DENY, "changed after approval")

        print("escape hatch")
        env_p = subprocess.run([sys.executable, "-B", str(GUARD)], capture_output=True, text=True, check=False,
                               input=json.dumps({"cwd": str(root), "tool_name": "Edit", "tool_input": {"file_path": "app/chart.js"}}),
                               env=dict(os.environ, CUPERTINO_DISABLE_GUARD="1", CLAUDE_PLUGIN_ROOT=str(PLUGIN)))
        ok = env_p.returncode == ALLOW
        failures += not ok
        print(f"  {'ok  ' if ok else 'FAIL'} CUPERTINO_DISABLE_GUARD=1 allows")

    print()
    print("ALL PASS" if not failures else f"{failures} FAILED")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
