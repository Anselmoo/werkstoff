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


def root_agreement() -> None:
    """The guard's stdlib find_state_root and repair_lib's must agree on every case, and a
    run begun at the repo root must govern a session working in a subdirectory."""
    global failures
    import importlib.util
    sys.path.insert(0, str(SCRIPTS))
    import repair_lib
    spec = importlib.util.spec_from_file_location("guard_mod", GUARD)
    guard_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(guard_mod)  # __name__ is not "__main__", so main() does not run
    print("state root: scripts and guard resolve the same .cupertino/")
    with tempfile.TemporaryDirectory() as td:
        repo = Path(td) / "repo"
        sub = repo / "dashboard" / "deep"
        sub.mkdir(parents=True)
        cases = [(sub, str(repo)), (sub, None), (repo, str(repo))]
        for state_at in (None, repo):
            if state_at is not None:
                (state_at / ".cupertino").mkdir(exist_ok=True)
            for start, proj in cases:
                a = Path(repair_lib.find_state_root(start, proj))
                b = Path(guard_mod.find_state_root(str(start), proj))
                ok = a == b
                failures += not ok
                print(f"  {'ok  ' if ok else 'FAIL'} agree: start={start.relative_to(td)} project_dir={'set' if proj else 'unset'}"
                      f" state={'present' if state_at else 'absent'} -> {a.relative_to(Path(td).parent) if a.is_relative_to(Path(td).parent) else a}")
        # The reviewer's case: CLAUDE_PROJECT_DIR = repo, session cwd = a subdirectory.
        (repo / "dashboard" / "a.css").write_text("x{}", encoding="utf-8")
        env = dict(os.environ, CLAUDE_PROJECT_DIR=str(repo))
        subprocess.run([sys.executable, str(SCRIPTS / "repair_state.py"), "begin", "r1"], cwd=sub, env=env,
                       capture_output=True, text=True, check=True)
        ok_marker = (repo / ".cupertino" / "repair" / "ACTIVE").is_file()
        failures += not ok_marker
        print(f"  {'ok  ' if ok_marker else 'FAIL'} a run begun from a subdirectory lands at the repo root")
        payload = {"cwd": str(sub), "tool_name": "Edit", "tool_input": {"file_path": "../a.css"}}
        p = subprocess.run([sys.executable, "-B", str(GUARD)], input=json.dumps(payload), capture_output=True, text=True,
                           env={**env, "CLAUDE_PLUGIN_ROOT": str(PLUGIN)}, check=False)
        ok = p.returncode == DENY and "objective.json" in p.stderr
        failures += not ok
        print(f"  {'ok  ' if ok else 'FAIL'} a session in a subdirectory is governed by that run (relative path resolved from the session)")


def state_root_boundary() -> None:
    """A .cupertino/ above the project must not govern it (review finding 5)."""
    global failures
    import importlib.util
    sys.path.insert(0, str(SCRIPTS))
    import repair_lib
    spec = importlib.util.spec_from_file_location("guard_mod2", GUARD)
    guard_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(guard_mod)
    print("state root stops at the project")
    with tempfile.TemporaryDirectory() as td:
        home = Path(td)
        (home / ".cupertino" / "repair").mkdir(parents=True)
        (home / ".cupertino" / "repair" / "ACTIVE").write_text("stale\n", encoding="utf-8")
        proj = home / "proj"
        (proj / "src").mkdir(parents=True)
        (proj / ".git").mkdir()
        for label, start, pd in (("CLAUDE_PROJECT_DIR set", proj / "src", str(proj)),
                                 ("no CLAUDE_PROJECT_DIR, .git marks the project", proj / "src", None)):
            for impl, fn in (("repair_lib", repair_lib.find_state_root), ("guard", guard_mod.find_state_root)):
                got = Path(fn(start if impl == "repair_lib" else str(start), pd))
                ok = got != home
                failures += not ok
                print(f"  {'ok  ' if ok else 'FAIL'} {impl}: an ancestor's .cupertino/ is ignored ({label}) -> {got}")
        (proj / ".cupertino").mkdir()
        got = Path(repair_lib.find_state_root(proj / "src", str(proj)))
        ok = got == proj
        failures += not ok
        print(f"  {'ok  ' if ok else 'FAIL'} the project's own .cupertino/ is still found from a subdirectory")
        p = subprocess.run([sys.executable, "-B", str(GUARD)], capture_output=True, text=True, check=False,
                           input=json.dumps({"cwd": str(proj / "src"), "tool_name": "Write",
                                             "tool_input": {"file_path": "a.py", "content": "x"}}),
                           env={**{k: v for k, v in os.environ.items() if k != "CUPERTINO_DISABLE_GUARD"},
                                "CLAUDE_PLUGIN_ROOT": str(PLUGIN), "CLAUDE_PROJECT_DIR": str(proj)})
        ok = p.returncode == ALLOW
        failures += not ok
        print(f"  {'ok  ' if ok else 'FAIL'} a stale ACTIVE in ~/.cupertino/ does not deny an edit in an unrelated project")


def main() -> int:
    global failures
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
        print("baseline taken: the objective is frozen")
        expect("rewriting the objective after baseline is denied", root, "Write",
               {"file_path": str(rdir / "objective.json"), "content": "{}"}, DENY, "frozen")
        expect("writing the changeset after baseline is still allowed", root, "Write",
               {"file_path": str(rdir / "changeset.json"), "content": "{}"}, ALLOW)
        (rdir / "changeset.json").write_text(json.dumps({"items": [
            {"id": "I1", "op": "modify", "paths": ["app/styles.css"], "rationale": "wrap"},
            {"id": "I2", "op": "delete", "paths": ["app/legacy.js"], "rationale": "dead", "evidence": "nothing imports it"},
            {"id": "I3", "op": "create", "paths": ["app/new.css"], "rationale": "split"},
            {"id": "I4", "op": "create", "paths": ["app/chart.js"], "rationale": "a create of a file that already exists"},
        ]}), encoding="utf-8")
        print("objective + baseline + changeset, not approved")
        expect("an edit before approval is denied", root, "Edit", {"file_path": "app/styles.css"}, DENY, "not been approved")

        print("approval is the user's")
        expect("the model running `repair_state.py approve` is denied, naming the ! prefix", root, "Bash",
               {"command": f"python3 {SCRIPTS}/repair_state.py approve"}, DENY, "`!` prefix")
        expect("... also when chained after another script", root, "Bash",
               {"command": f"python3 {SCRIPTS}/repair_state.py status && python3 {SCRIPTS}/repair_state.py approve"},
               DENY, "user's decision")
        p = subprocess.run([sys.executable, "-B", str(GUARD)], capture_output=True, text=True, check=False,
                           input=json.dumps({"cwd": str(root), "tool_name": "Bash",
                                             "tool_input": {"command": f"python3 {SCRIPTS}/repair_state.py approve"}}),
                           env={**{k: v for k, v in os.environ.items() if k not in ("CUPERTINO_DISABLE_GUARD", "CLAUDE_PROJECT_DIR")},
                                "CLAUDE_PLUGIN_ROOT": str(PLUGIN), "CUPERTINO_REPAIR_PREAPPROVED": "1"})
        ok = p.returncode == ALLOW
        failures += not ok
        print(f"  {'ok  ' if ok else 'FAIL'} a human's standing approval in the hook's environment allows it")
        expect("an inline VAR=1 in the command does not count as that approval", root, "Bash",
               {"command": f"CUPERTINO_REPAIR_PREAPPROVED=1 python3 {SCRIPTS}/repair_state.py approve"}, DENY, "user's decision")
        script(root, "repair_state.py", "approve")  # the user, outside the hook
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

        print("shell routes around the scope (review findings 1 and 2)")
        for name, cmd in (
            ("a plugin script piped into tee", f"python3 {SCRIPTS}/verify.py | tee app/chart.js"),
            ("a redirect hidden behind a comment naming the plugin", "echo x > app/chart.js # cupertino/scripts/"),
            ("rm on a path that merely contains cupertino and /scripts/", "rm -rf /tmp/cupertino-app/scripts/../src"),
            ("a plugin script then a newline then rm", f"python3 {SCRIPTS}/verify.py\nrm app/chart.js"),
            ("a plugin script with a command substitution", f"python3 {SCRIPTS}/verify.py --run $(rm app/chart.js)"),
            ("a script outside the plugin with the same name", "python3 /tmp/cupertino/scripts/verify.py && cp a app/chart.js"),
            ("build_repair_html --out onto a source file", f"python3 {SCRIPTS}/build_repair_html.py --run t1 --out app/chart.js"),
            ("1> redirect", "echo x 1>app/chart.js"),
            ("&> redirect", "echo x &>app/chart.js"),
            (">| clobber redirect", "echo x >| app/chart.js"),
            ("sed with -i after a non-flag argument", "sed -e s/a/b/ -i app/chart.js"),
            ("sed --in-place", "sed --in-place s/a/b/ app/chart.js"),
            ("python -c opening a file for writing", "python3 -c \"open('app/chart.js','w').write('x')\""),
            ("python -c Path.write_text", "python3 -c \"import pathlib; pathlib.Path('app/chart.js').write_text('x')\""),
            ("node -e fs.writeFileSync", "node -e \"require('fs').writeFileSync('app/chart.js','x')\""),
            ("find -exec", "find app -name '*.js' -exec truncate -s0 {} +"),
        ):
            expect(f"denied: {name}", root, "Bash", {"command": cmd}, DENY)
        expect("allowed: 2>&1 and 2>/dev/null are not writes", root, "Bash",
               {"command": "grep -rn kpis app 2>&1 | head; ls app 2>/dev/null"}, ALLOW)
        expect("allowed: build_repair_html --out inside .cupertino/", root, "Bash",
               {"command": f"python3 {SCRIPTS}/build_repair_html.py --run t1 --out .cupertino/repair/t1/report.html"}, ALLOW)
        expect("allowed: two plugin scripts chained", root, "Bash",
               {"command": f"python3 -B {SCRIPTS}/repair_state.py status && python3 {SCRIPTS}/verify.py --no-report"}, ALLOW)

        print("forging the run's state (review findings 3 and 4)")
        rep_dir = root / ".cupertino" / "repair"
        for name, target in (
            ("the ACTIVE marker", rep_dir / "ACTIVE"),
            ("another run's approval", rep_dir / "fake" / "approved"),
            ("another run's objective", rep_dir / "fake" / "objective.json"),
            ("another run's baseline", rep_dir / "fake" / "baseline" / "baseline.json"),
            ("the round log the HALT counts", rdir / "verdicts.jsonl"),
            ("the applied log", rdir / "applied.jsonl"),
        ):
            expect(f"Write to {name} is denied", root, "Write", {"file_path": str(target), "content": ""}, DENY,
                   "written only by the repair scripts")
        expect("a shell write to the ACTIVE marker is denied", root, "Bash",
               {"command": "echo fake > .cupertino/repair/ACTIVE"}, DENY)
        expect("emptying the round log from the shell is denied", root, "Bash",
               {"command": f"truncate -s0 {rdir}/verdicts.jsonl"}, DENY)

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
        expect("a second write to the file the item just created is allowed (review finding 9)", root, "Edit",
               {"file_path": "app/new.css"}, ALLOW)

        script(root, "repair_state.py", "finish-item", "I3")
        script(root, "repair_state.py", "start-item", "I4")
        print("item I4 (create app/chart.js, which existed at baseline) active")
        expect("a create over a file that existed at baseline is denied", root, "Write",
               {"file_path": "app/chart.js", "content": "x"}, DENY, "existed when the baseline was taken")

        script(root, "repair_state.py", "finish-item", "I4")
        (rdir / "changeset.json").write_text(json.dumps({"items": [
            {"id": "I1", "op": "modify", "paths": ["app/styles.css", "app/chart.js"], "rationale": "sneak"}]}), encoding="utf-8")
        print("changeset edited after approval")
        script_env = dict(os.environ, CLAUDE_PROJECT_DIR=str(root))
        p = subprocess.run([sys.executable, str(SCRIPTS / "repair_state.py"), "start-item", "I1"], cwd=root, env=script_env,
                           capture_output=True, text=True, check=False)
        ok = p.returncode == 1 and "changed after approval" in p.stderr
        failures += not ok
        print(f"  {'ok  ' if ok else 'FAIL'} start-item refuses a changeset edited after approval")
        (rdir / "active-item").write_text("I1\n", encoding="utf-8")
        expect("the guard refuses it too, even with an active-item file planted", root, "Edit", {"file_path": "app/chart.js"},
               DENY, "changed after approval")

        print("objective edited around the guard")
        objective = (rdir / "objective.json").read_text(encoding="utf-8")
        (rdir / "objective.json").write_text(objective.replace("chart untouched", "chart may change"), encoding="utf-8")
        env_p2 = dict(os.environ, CLAUDE_PROJECT_DIR=str(root))
        for name, args in (("approve", ["repair_state.py", "approve"]), ("verify", ["verify.py", "--no-report"])):
            p = subprocess.run([sys.executable, str(SCRIPTS / args[0]), *args[1:]], cwd=root, env=env_p2,
                               capture_output=True, text=True, check=False)
            ok = p.returncode != 0 and "objective.json changed after the baseline" in p.stderr
            failures += not ok
            print(f"  {'ok  ' if ok else 'FAIL'} {name} refuses an objective changed after the baseline")
        (rdir / "objective.json").write_text(objective, encoding="utf-8")

        print("escape hatch")
        env_p = subprocess.run([sys.executable, "-B", str(GUARD)], capture_output=True, text=True, check=False,
                               input=json.dumps({"cwd": str(root), "tool_name": "Edit", "tool_input": {"file_path": "app/chart.js"}}),
                               env=dict(os.environ, CUPERTINO_DISABLE_GUARD="1", CLAUDE_PLUGIN_ROOT=str(PLUGIN)))
        ok = env_p.returncode == ALLOW
        failures += not ok
        print(f"  {'ok  ' if ok else 'FAIL'} CUPERTINO_DISABLE_GUARD=1 allows")

    root_agreement()
    state_root_boundary()
    print()
    print("ALL PASS" if not failures else f"{failures} FAILED")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
