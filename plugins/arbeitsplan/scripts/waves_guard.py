#!/usr/bin/env python3
"""PreToolUse guard for the agents an arbeitsplan multi-wave install generates (#106 R10).

usage: <name>_guard.py --paths | --runner | --selftest   (hook event JSON on stdin)

VENDORED. install_waves.py copies this file into a project as
.claude/hooks/<name>_guard.py and wires it into every generated agent's
frontmatter `hooks:` -- a hook, never a permission rule, because a relative deny
rule in project settings did not resolve inside agent worktrees. It reads
../workflows/<name>.plan.json, located from THIS file, never from the cwd: a
worktree's cwd is not the project root, and $CLAUDE_PROJECT_DIR (which is) is
only how the hook command finds this file.

  --paths   Write/Edit/MultiEdit/NotebookEdit: deny a target inside the plan's
            `offLimits`. The path is made absolute from the event's `cwd` and
            normalised LEXICALLY (os.path.normpath, the host's own flavour) --
            Path.resolve() would follow symlinks and change what is decided --
            then taken relative to the git tree that contains it, so the same
            glob holds in the primary checkout and in every agent worktree. On a
            case-insensitive filesystem (macOS, Windows) both sides are
            case-folded, or `Secrets/x` would walk past `secrets/**`.
  --runner  Bash, for the generated runner agent only: the command must match a
            declared template exactly ({placeholder} slots take ids, branch names
            and paths only), and a dispatch runs ONE command -- an O_EXCL ledger
            keyed on the hook input's agent_id denies a second.

Protocol: deny = exit 2 + stdout JSON (hookEventName, permissionDecision,
permissionDecisionReason) + the reason on stderr; allow = exit 0, no output.
Fail CLOSED: any error denies. The generated hook command appends `|| exit 2`,
so an interpreter that cannot even start this file denies too, rather than the
runtime reading a crash as "not blocked".
Escape hatch: ARBEITSPLAN_WAVES_DISABLE_GUARD=1.

STDLIB ONLY. Python >= 3.10.
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import NoReturn

EDIT_TOOLS = ("Write", "Edit", "MultiEdit", "NotebookEdit")
SAFE_VALUE = r"[A-Za-z0-9._/,=:@+-]+"
PLACEHOLDER = re.compile(r"\{([A-Za-z][A-Za-z0-9_]*)\}")
ESCAPE = "Set ARBEITSPLAN_WAVES_DISABLE_GUARD=1 to bypass it deliberately."


def deny(reason: str) -> NoReturn:
    sys.stdout.write(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse", "permissionDecision": "deny",
        "permissionDecisionReason": reason}}))
    sys.stdout.flush()
    print(reason, file=sys.stderr)
    sys.exit(2)


def allow() -> NoReturn:
    sys.exit(0)


def plan_file() -> Path:
    here = Path(__file__).resolve()
    return here.parent.parent / "workflows" / (here.stem.removesuffix("_guard") + ".plan.json")


def casefolds() -> bool:
    if os.environ.get("ARBEITSPLAN_WAVES_CASEFOLD") in ("0", "1"):
        return os.environ["ARBEITSPLAN_WAVES_CASEFOLD"] == "1"
    return sys.platform in ("darwin", "win32") or os.path.normcase("A") == "a"


def tree_root(abs_path: str) -> str | None:
    """The nearest ancestor holding a `.git` entry (a directory in the primary
    checkout, a file in a linked worktree)."""
    cur = Path(abs_path).parent
    while True:
        if (cur / ".git").exists():
            return str(cur)
        if cur.parent == cur:
            return None
        cur = cur.parent


def edit_targets(tool_input: dict) -> list:
    found = []
    for key in ("file_path", "notebook_path"):
        val = tool_input.get(key)
        if isinstance(val, str) and val:
            found.append(val)
    edits = tool_input.get("edits")
    if isinstance(edits, list):
        for e in edits:
            if isinstance(e, dict) and isinstance(e.get("file_path"), str) and e["file_path"]:
                found.append(e["file_path"])
    return found


def off_limits(rel: str, globs: list, fold: bool) -> str | None:
    rel = rel.replace(os.sep, "/")
    base = rel.rsplit("/", 1)[-1]
    if fold:
        rel, base = rel.lower(), base.lower()
    for raw in globs:
        pat = raw.replace("**/", "*/").replace("**", "*")
        if fold:
            pat = pat.lower()
        if fnmatch.fnmatchcase(rel, pat) or ("/" not in raw and fnmatch.fnmatchcase(base, pat)):
            return raw
    return None


def check_paths(event: dict, plan: dict) -> NoReturn:
    if event.get("tool_name") not in EDIT_TOOLS:
        allow()
    targets = edit_targets(event.get("tool_input") or {})
    if not targets:
        deny(f"arbeitsplan-waves: an edit with no determinable path cannot be checked against "
             f"offLimits. {ESCAPE}")
    cwd = event.get("cwd") or str(Path.cwd())
    fold = casefolds()
    for raw in targets:
        # normpath, not Path.resolve(): lexical, deliberately -- see the module
        # docstring. Path has no lexical '..' collapse, so this one stays os.path.
        abs_path = os.path.normpath(raw if Path(raw).is_absolute() else str(Path(cwd) / raw))
        root = tree_root(abs_path)
        if root is None:
            continue  # outside every git tree (a smoke scratch dir): not the plan's to police
        rel = os.path.relpath(abs_path, root)
        if rel == ".." or rel.startswith(".." + os.sep):
            continue
        hit = off_limits(rel, plan.get("offLimits") or [], fold)
        if hit:
            deny(f"arbeitsplan-waves: {rel!r} is off limits for this plan ({hit!r} in "
                 f"{plan_file().name}'s offLimits). {ESCAPE}")
    allow()


def template_regex(template: str) -> re.Pattern:
    parts, pos = [], 0
    for m in PLACEHOLDER.finditer(template):
        parts.append(re.escape(template[pos:m.start()]))
        parts.append(SAFE_VALUE)
        pos = m.end()
    parts.append(re.escape(template[pos:]))
    return re.compile("".join(parts))


def runner_templates(plan: dict) -> list:
    out = [n["script"]["command"] for n in plan.get("nodes") or []
           if isinstance(n, dict) and isinstance(n.get("script"), dict)
           and isinstance(n["script"].get("command"), str)]
    out.extend(v for v in (plan.get("helper") or {}).values() if isinstance(v, str))
    return out


def check_runner(event: dict, plan: dict) -> NoReturn:
    if event.get("tool_name") != "Bash":
        deny(f"arbeitsplan-waves: the runner may only call Bash. {ESCAPE}")
    cmd = (event.get("tool_input") or {}).get("command")
    templates = runner_templates(plan)
    if not isinstance(cmd, str) or not any(template_regex(t).fullmatch(cmd.strip())
                                           for t in templates):
        deny(f"arbeitsplan-waves: the runner may run only a command the plan declares; {cmd!r} "
             f"matches none of {templates}. {ESCAPE}")
    agent_id = event.get("agent_id")
    if not isinstance(agent_id, str) or not agent_id:
        deny(f"arbeitsplan-waves: a runner call without agent_id cannot be held to one command. "
             f"{ESCAPE}")
    ledger = plan_file().with_suffix("").with_suffix(".runner")
    ledger.mkdir(parents=True, exist_ok=True)
    entry = ledger / (hashlib.sha256(agent_id.encode()).hexdigest()[:32] + ".json")
    try:
        fd = os.open(entry, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    except FileExistsError:
        deny(f"arbeitsplan-waves: this runner dispatch already ran its one command. {ESCAPE}")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump({"agent_id": agent_id, "command": cmd}, fh)
    allow()


def main(argv: list) -> NoReturn:
    import argparse

    parser = argparse.ArgumentParser(prog=Path(__file__).name, description=(
        __doc__ or "").split("\n\n")[0], epilog="exit 0 allow, 2 deny (and on any error)")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--paths", action="store_true", help="judge an edit against offLimits")
    group.add_argument("--runner", action="store_true", help="judge the runner's Bash call")
    group.add_argument("--selftest", action="store_true", help="run the selftest")
    try:
        args = parser.parse_args(argv)
    except SystemExit:
        deny(f"arbeitsplan-waves: the guard was invoked with {argv!r}, which is not a mode it "
             f"has; refusing rather than allowing the call unchecked. {ESCAPE}")
    if args.selftest:
        sys.exit(selftest())
    mode = "--paths" if args.paths else "--runner"
    if os.environ.get("ARBEITSPLAN_WAVES_DISABLE_GUARD") == "1":
        allow()
    try:
        if mode not in ("--paths", "--runner"):
            raise ValueError(f"unknown mode {mode!r}")
        event = json.load(sys.stdin)
        plan = json.loads(plan_file().read_text(encoding="utf-8"))
        if mode == "--paths":
            check_paths(event, plan)
        check_runner(event, plan)
    except SystemExit:
        raise
    except Exception as exc:  # fail closed
        deny(f"arbeitsplan-waves: the guard could not evaluate this call "
             f"({type(exc).__name__}: {exc}); refusing rather than allowing it unchecked. {ESCAPE}")


def selftest() -> int:
    import subprocess
    import tempfile

    fails: list = []
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "proj"
        (root / ".git").mkdir(parents=True)
        hooks, wf = root / ".claude" / "hooks", root / ".claude" / "workflows"
        hooks.mkdir(parents=True)
        wf.mkdir(parents=True)
        guard = hooks / "demo_guard.py"
        guard.write_text(Path(__file__).read_text(encoding="utf-8"), encoding="utf-8")
        (wf / "demo.plan.json").write_text(json.dumps({
            "offLimits": ["secrets/**", "*.pem"],
            "nodes": [{"id": "g", "script": {"command": "python3 x_state.py merge --wave {wave}"}}],
            "helper": {"record": "python3 x_state.py record --row {row}"}}))
        tree = Path(tmp) / "wt"
        tree.mkdir()
        (tree / ".git").write_text("gitdir: elsewhere\n")

        def run(mode: str, event: dict, env: dict | None = None) -> int:
            return subprocess.run([sys.executable, str(guard), mode], input=json.dumps(event),
                                  capture_output=True, text=True,
                                  env={**os.environ, "ARBEITSPLAN_WAVES_CASEFOLD": "0",
                                       **(env or {})}).returncode

        def edit(path: str, cwd: Path = root) -> dict:
            return {"cwd": str(cwd), "tool_name": "Edit", "tool_input": {"file_path": path}}

        cases = [
            ("paths: off-limits file in the primary checkout", run("--paths", edit("secrets/k")), 2),
            ("paths: an ordinary file", run("--paths", edit("src/a.go")), 0),
            ("paths: off-limits file from a worktree's cwd", run("--paths", edit("secrets/k", tree)),
             2),
            ("paths: absolute path into a worktree", run("--paths", edit(str(tree / "secrets/k"))),
             2),
            ("paths: '..' collapsed lexically into secrets", run("--paths", edit(
                "src/../secrets/k")), 2),
            ("paths: basename glob anywhere", run("--paths", edit("deploy/prod.pem")), 2),
            ("paths: case variant, case-insensitive filesystem", run(
                "--paths", edit("Secrets/k"), {"ARBEITSPLAN_WAVES_CASEFOLD": "1"}), 2),
            ("paths: case variant, case-sensitive filesystem", run("--paths", edit("Secrets/k")), 0),
            ("paths: outside every git tree (a scratch dir)", run("--paths", edit(
                str(Path(tmp) / "scratch" / "secrets" / "k"))), 0),
            ("paths: MultiEdit carrying one off-limits path", run("--paths", {
                "cwd": str(root), "tool_name": "MultiEdit", "tool_input": {"edits": [
                    {"file_path": "src/a"}, {"file_path": "secrets/b"}]}}), 2),
            ("paths: no determinable path", run("--paths", {"cwd": str(root), "tool_name": "Edit",
                                                             "tool_input": {}}), 2),
            ("runner: declared command", run("--runner", {"tool_name": "Bash", "agent_id": "a1",
                "tool_input": {"command": "python3 x_state.py merge --wave 2"}}), 0),
            ("runner: second command, same dispatch", run("--runner", {"tool_name": "Bash",
                "agent_id": "a1", "tool_input": {"command": "python3 x_state.py merge --wave 2"}}),
             2),
            ("runner: helper template", run("--runner", {"tool_name": "Bash", "agent_id": "a2",
                "tool_input": {"command": "python3 x_state.py record --row w1-a"}}), 0),
            ("runner: undeclared command", run("--runner", {"tool_name": "Bash", "agent_id": "a3",
                "tool_input": {"command": "rm -rf ."}}), 2),
            ("runner: placeholder carrying a space", run("--runner", {"tool_name": "Bash",
                "agent_id": "a4", "tool_input": {"command": "python3 x_state.py merge --wave 2 x"}}),
             2),
            ("runner: no agent_id", run("--runner", {"tool_name": "Bash", "tool_input": {
                "command": "python3 x_state.py merge --wave 2"}}), 2),
            ("runner: a tool other than Bash", run("--runner", {"tool_name": "Write",
                "agent_id": "a5", "tool_input": {"file_path": "x"}}), 2),
            ("unknown mode fails closed", run("--nope", {}), 2),
            ("escape hatch", run("--paths", edit("secrets/k"),
                                 {"ARBEITSPLAN_WAVES_DISABLE_GUARD": "1"}), 0),
        ]
        for name, got, want in cases:
            ok = got == want
            print(f"  {'ok  ' if ok else 'FAIL'} {name}: exit {got}")
            if not ok:
                fails.append(name)
        proc = subprocess.run([sys.executable, str(guard), "--paths"], input=json.dumps(
            edit("secrets/k")), capture_output=True, text=True,
            env={**os.environ, "ARBEITSPLAN_WAVES_CASEFOLD": "0"})
        payload = json.loads(proc.stdout or "{}").get("hookSpecificOutput", {})
        if not (payload.get("hookEventName") == "PreToolUse" and payload.get(
                "permissionDecision") == "deny" and payload.get("permissionDecisionReason")
                and proc.stderr.strip()):
            fails.append("deny protocol: exit 2 + hookEventName JSON + stderr")
            print("  FAIL deny protocol")
        else:
            print("  ok   deny protocol: exit 2 + hookEventName JSON + stderr")
    print()
    if fails:
        print(f"SELFTEST FAILED ({len(fails)}): " + ", ".join(fails))
        return 1
    print("waves_guard selftest passed (denies AND allows)")
    return 0


if __name__ == "__main__":
    main(sys.argv[1:])
