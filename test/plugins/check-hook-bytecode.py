#!/usr/bin/env python3
"""A plugin must not write bytecode into its installed copy (#88).

A hook that loads a sibling module makes CPython write `__pycache__` next to
that source. For an installed plugin the source is the copy under
`~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/`, so every hook run
makes the installed copy diverge from the tree it was installed from.

This check inspects an INSTALLED COPY, never the source tree: each plugin that
ships `hooks/hooks.json` is copied into a fake cache laid out exactly like the
real one, every declared command is run against that copy with
`${CLAUDE_PLUGIN_ROOT}` pointing at it, and the copy is then searched for
bytecode.

WHY "NO __pycache__" IS NOT ENOUGH ON ITS OWN
---------------------------------------------
An empty result proves nothing if the probe never reached a sibling import --
a hook that exits early, a probe whose command failed to start, or a copy
that was never populated would all leave a spotless cache. So the probe also
proves it ran: a `sitecustomize` on the child's PYTHONPATH installs an audit
hook that logs every `.py` file opened inside the copy. The check requires
that arbeitsplan's guard was seen opening `scripts/delegation.py` -- the
sibling import #88 cites -- and reports INSTRUMENT-DEAD otherwise. The proof
is independent of `-B` and of `sys.dont_write_bytecode`, so it neither
depends on the defect being present nor penalises a belt-and-braces fix.

`PYTHONDONTWRITEBYTECODE` is stripped from the child's environment: a CI
runner or a user shell that sets it would make this check pass vacuously.

Also checks, statically, that every `python3` hook command carries `-B`.

SKILL-, COMMAND- AND WORKFLOW-INVOKED SCRIPTS
---------------------------------------------
Hooks are not the only way a plugin runs Python: skills, commands and workflow
prompts tell the model to run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/x.py"`,
and a script that imports a sibling (befund_cli.py imports its `lib/` package)
writes bytecode into the installed copy exactly as a hook does. So the same
installed copies are also checked for every such invocation in a `.md` or `.js`
file of the plugin:

- statically, the invocation carries `-B`, and its `${CLAUDE_PLUGIN_ROOT}` path is
  double-quoted (it is substituted as a literal absolute path, which may contain
  a space -- the same rule applies to hooks.json commands), and typed as a
  command rather than stored in a shell variable (`GUARD="python3 ..."` then
  `$GUARD args` word-splits on expansion however the value was quoted);
- it is still PERMITTED by its skill's `allowed-tools`: a frontmatter
  `Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/x.py:*)` is a prefix match on the
  command the model types, so a body that says `python3 -B ...` against a
  pattern that says `python3 ...` turns every call into a permission prompt;
- at runtime, each distinct script is run in the installed copy with the
  interpreter flags AS WRITTEN and `--help` (stdin closed, a scratch cwd), and
  the copy is searched for bytecode afterwards. The same audit hook must see
  befund_cli.py open a module of its sibling `scripts/lib/` package, or the
  script half reports INSTRUMENT-DEAD too.

Usage:
    python3 test/plugins/check-hook-bytecode.py [--plugins-root plugins] [-v]

Exit 0 when no copy gained bytecode and the probe is proven live; 1 otherwise.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MARKETPLACE = "werkstoff"

# The sibling import #88 cites. The probe must be seen opening this file in
# the installed copy, or the whole check is measuring nothing.
REQUIRED_PROOF = ("arbeitsplan", "scripts/delegation.py")

# The script-invocation half's proof: befund_cli.py imports its `lib/` package
# at module level, so even `--help` must be seen opening a file inside it.
REQUIRED_SCRIPT_PROOF = ("befund", "scripts/lib/")

# `python3 [flags] ${CLAUDE_PLUGIN_ROOT}/<script>.py`, with the path bare, quoted,
# or quoted with YAML-escaped quotes (`\"...\"`, as frontmatter writes it).
INVOCATION = re.compile(
    r'(?P<py>\bpython3?)(?P<flags>(?:[ \t]+-[A-Za-z0-9]+)*)[ \t]+(?P<q>\\?"?)'
    r"\$\{CLAUDE_PLUGIN_ROOT\}/(?P<script>[A-Za-z0-9_./-]+?\.py)"
)
SCANNED_SUFFIXES = {".md", ".js"}

# Claude Code substitutes ${CLAUDE_PLUGIN_ROOT} textually before the model (or
# the hook shell) sees it, so the model types a literal absolute path. Under a
# home directory or relocated plugin cache with a space in it, an unquoted path
# splits into two shell words; the plugin docs say to wrap it in double quotes.
QUOTED_ROOT = '"${CLAUDE_PLUGIN_ROOT}'

BASH_PATTERN = re.compile(r"Bash\(([^)]*)\)")

# `GUARD="python3 -B ${CLAUDE_PLUGIN_ROOT}/x.py"` then `$GUARD args`: no quoting
# inside the value survives, because the shell does not re-parse quotes in an
# expanded variable -- `$GUARD` word-splits the literal path however it was
# written. The quoting rule above would pass a quoted value, so this is its own rule.
STORED_IN_VARIABLE = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*=[\"']?$")

SITECUSTOMIZE = """
import os, sys
_root = os.environ.get("HOOK_BYTECODE_PROBE_ROOT", "")
_log = os.environ.get("HOOK_BYTECODE_PROBE_LOG", "")
def _audit(event, args):
    if event != "open" or not _root or not _log:
        return
    path = args[0] if args else None
    if isinstance(path, bytes):
        path = os.fsdecode(path)
    if isinstance(path, str) and path.endswith(".py") and path.startswith(_root):
        with open(_log, "a", encoding="utf-8") as fh:
            fh.write(path + "\\n")
if _root and _log:
    sys.addaudithook(_audit)
"""

PAYLOAD = {
    "hook_event_name": "PreToolUse",
    "tool_name": "Read",
    "tool_input": {"file_path": "README.md"},
    "session_id": "hook-bytecode-probe",
    "cwd": "",
}


def plugin_version(plugin: Path) -> str:
    manifest = plugin / ".claude-plugin" / "plugin.json"
    try:
        return str(json.loads(manifest.read_text(encoding="utf-8"))["version"])
    except (OSError, ValueError, KeyError):
        return "0.0.0"


def declared_commands(hooks_json: Path) -> list[tuple[str, str]]:
    """Every (event, raw command string) a hooks.json declares, all events."""
    data = json.loads(hooks_json.read_text(encoding="utf-8"))
    found = []
    for event, entries in (data.get("hooks") or {}).items():
        for entry in entries or []:
            for hook in entry.get("hooks", []):
                if hook.get("type") == "command" and hook.get("command"):
                    found.append((event, hook["command"]))
    return found


def missing_dash_b(raw: str) -> bool:
    words = shlex.split(raw)
    if not words or not Path(words[0]).name.startswith("python"):
        return False
    # Interpreter flags come before the script path; -B may be combined (-Bu).
    for word in words[1:]:
        if not word.startswith("-"):
            break
        if word.startswith("-") and not word.startswith("--") and "B" in word[1:]:
            return False
    return True


def flags_carry_b(flags: str) -> bool:
    """True when interpreter flags such as ' -B' or ' -Bu' include -B."""
    return any(
        w.startswith("-") and not w.startswith("--") and "B" in w[1:]
        for w in flags.split()
    )


def script_invocations(plugin: Path) -> list[tuple[Path, int, str, str, str]]:
    """(file, line, command-as-written, flags, script) for every
    `python3 ... ${CLAUDE_PLUGIN_ROOT}/<script>.py` in the plugin's .md/.js."""
    found = []
    for path in sorted(plugin.rglob("*")):
        if path.suffix not in SCANNED_SUFFIXES or not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for m in INVOCATION.finditer(text):
            line = text.count("\n", 0, m.start()) + 1
            command = m.group(0).replace('\\"', '"')
            found.append((path, line, command, m.group("flags"), m.group("script")))
    return found


def stored_in_variable(plugin: Path) -> list[str]:
    """Invocations assigned to a shell variable instead of typed as a command."""
    problems = []
    for path in sorted(plugin.rglob("*")):
        if path.suffix not in SCANNED_SUFFIXES or not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for m in INVOCATION.finditer(text):
            prefix = text[text.rfind("\n", 0, m.start()) + 1 : m.start()]
            if STORED_IN_VARIABLE.search(prefix):
                line = text.count("\n", 0, m.start()) + 1
                problems.append(
                    f"{path.relative_to(plugin.parent)}:{line}: plugin-root command stored "
                    f"in a shell variable (word-splits on expansion): {prefix.strip()}"
                )
    return problems


def unpermitted(plugin: Path) -> list[str]:
    """Invocations a skill's own Bash(...) allowed-tools patterns would not
    permit. Only files whose frontmatter restricts Bash to patterns are checked;
    a pattern `x:*` permits commands starting with `x`, anything else exactly."""
    problems = []
    for path in sorted(plugin.rglob("*.md")):
        text = path.read_text(encoding="utf-8", errors="replace")
        if not text.startswith("---"):
            continue
        front, _, body = text[3:].partition("\n---")
        allowed = next(
            (ln for ln in front.splitlines() if ln.startswith("allowed-tools:")), ""
        )
        patterns = [p.replace('\\"', '"') for p in BASH_PATTERN.findall(allowed)]
        if not patterns:
            continue
        body_start = len(front) + 7
        for m in INVOCATION.finditer(body):
            command = m.group(0).replace('\\"', '"')
            if m.group("q"):
                command += '"'
            ok = any(
                command.startswith(p[:-2]) if p.endswith(":*") else command == p
                for p in patterns
            )
            if not ok:
                line = text.count("\n", 0, body_start + m.start()) + 1
                problems.append(
                    f"{path.relative_to(plugin.parent)}:{line}: `{command}` is not permitted "
                    f"by its allowed-tools Bash patterns {patterns}"
                )
    return problems


def run_script(
    flags: str, script: Path, workdir: Path, env: dict[str, str]
) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            ["python3", *flags.split(), str(script), "--help"],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            cwd=workdir,
            env=env,
            timeout=30,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return None


def probe_env(copy: Path, workdir: Path, site_dir: Path, log: Path) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k != "PYTHONDONTWRITEBYTECODE"}
    env.update(
        {
            "CLAUDE_PLUGIN_ROOT": str(copy),
            "CLAUDE_PROJECT_DIR": str(workdir),
            "PYTHONPATH": str(site_dir),
            "HOOK_BYTECODE_PROBE_ROOT": str(copy),
            "HOOK_BYTECODE_PROBE_LOG": str(log),
        }
    )
    return env


def bytecode_in(tree: Path) -> list[Path]:
    hits = [p for p in tree.rglob("__pycache__") if p.is_dir()]
    hits += [p for p in tree.rglob("*.pyc") if p.parent.name != "__pycache__"]
    return sorted(hits)


def install_copy(plugin: Path, cache: Path) -> Path:
    dest = cache / MARKETPLACE / plugin.name / plugin_version(plugin)
    shutil.copytree(plugin, dest, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    return dest


def probe(
    raw: str, event: str, copy: Path, workdir: Path, site_dir: Path, log: Path
) -> subprocess.CompletedProcess[str]:
    argv = [w.replace("${CLAUDE_PLUGIN_ROOT}", str(copy)) for w in shlex.split(raw)]
    env = {k: v for k, v in os.environ.items() if k != "PYTHONDONTWRITEBYTECODE"}
    env.update(
        {
            "CLAUDE_PLUGIN_ROOT": str(copy),
            "CLAUDE_PROJECT_DIR": str(workdir),
            "PYTHONPATH": str(site_dir),
            "HOOK_BYTECODE_PROBE_ROOT": str(copy),
            "HOOK_BYTECODE_PROBE_LOG": str(log),
        }
    )
    payload = dict(PAYLOAD, hook_event_name=event, cwd=str(workdir))
    return subprocess.run(
        argv,
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        cwd=workdir,
        env=env,
        timeout=60,
        check=False,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--plugins-root", default=str(REPO / "plugins"))
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    plugins = sorted(
        p.parent.parent for p in Path(args.plugins_root).glob("*/hooks/hooks.json")
    )
    if not plugins:
        print("FAIL no plugins/*/hooks/hooks.json found -- nothing was probed")
        return 1
    all_plugins = sorted(
        p.parent.parent
        for p in Path(args.plugins_root).glob("*/.claude-plugin/plugin.json")
    )

    failures: list[str] = []
    opened: dict[str, set[str]] = {}
    script_opened: dict[str, set[str]] = {}
    probes = 0
    script_runs = 0
    invocation_count = 0

    with tempfile.TemporaryDirectory(prefix="hook-bytecode-") as tmp:
        tmp_path = Path(tmp)
        cache = tmp_path / ".claude" / "plugins" / "cache"
        site_dir = tmp_path / "site"
        site_dir.mkdir()
        (site_dir / "sitecustomize.py").write_text(SITECUSTOMIZE, encoding="utf-8")

        for plugin in plugins:
            copy = install_copy(plugin, cache)
            try:
                commands = declared_commands(copy / "hooks" / "hooks.json")
            except (OSError, ValueError) as exc:
                failures.append(f"{plugin.name}: hooks.json unreadable ({exc})")
                continue
            log = tmp_path / f"{plugin.name}.opened"
            for event, raw in commands:
                if missing_dash_b(raw):
                    failures.append(f"{plugin.name}: hook command lacks -B: {raw}")
                if QUOTED_ROOT not in raw:
                    failures.append(
                        f"{plugin.name}: hook plugin-root path unquoted: {raw}"
                    )
                workdir = tmp_path / "work" / f"{plugin.name}-{probes}"
                workdir.mkdir(parents=True)
                result = probe(raw, event, copy, workdir, site_dir, log)
                probes += 1
                if args.verbose:
                    print(f"  probe {plugin.name} {event}: exit {result.returncode}")
            if log.is_file():
                opened[plugin.name] = {
                    Path(line).relative_to(copy).as_posix()
                    for line in log.read_text(encoding="utf-8").split()
                }
            for hit in bytecode_in(copy):
                failures.append(
                    f"{plugin.name}: installed copy gained bytecode: "
                    f"{hit.relative_to(cache).as_posix()}"
                )

        # Second half: scripts that skills, commands and workflows invoke.
        scripts_cache = tmp_path / "scripts-cache" / ".claude" / "plugins" / "cache"
        for plugin in all_plugins:
            invocations = script_invocations(plugin)
            invocation_count += len(invocations)
            for path, line, command, flags, _script in invocations:
                if not flags_carry_b(flags):
                    failures.append(
                        f"{path.relative_to(plugin.parent)}:{line}: invocation lacks -B: "
                        f"{command}"
                    )
                if QUOTED_ROOT not in command:
                    failures.append(
                        f"{path.relative_to(plugin.parent)}:{line}: plugin-root path unquoted: "
                        f"{command}"
                    )
            failures.extend(stored_in_variable(plugin))
            failures.extend(unpermitted(plugin))
            if not invocations:
                continue
            copy = install_copy(plugin, scripts_cache)
            log = tmp_path / f"{plugin.name}.scripts.opened"
            for flags, script in sorted(
                {(f.strip(), s) for _, _, _, f, s in invocations}
            ):
                target = copy / script
                if not target.is_file():
                    continue
                workdir = tmp_path / "script-work" / f"{plugin.name}-{script_runs}"
                workdir.mkdir(parents=True)
                result = run_script(
                    flags, target, workdir, probe_env(copy, workdir, site_dir, log)
                )
                script_runs += 1
                if args.verbose:
                    rc = "timeout" if result is None else result.returncode
                    print(
                        f"  script {plugin.name} python3 {flags} {script} --help: {rc}"
                    )
            if log.is_file():
                script_opened[plugin.name] = {
                    Path(line).relative_to(copy).as_posix()
                    for line in log.read_text(encoding="utf-8").split()
                }
            for hit in bytecode_in(copy):
                failures.append(
                    f"{plugin.name}: a skill-invoked script wrote bytecode into the installed "
                    f"copy: {hit.relative_to(scripts_cache).as_posix()}"
                )

    name, sibling = REQUIRED_PROOF
    if sibling not in opened.get(name, set()):
        print(
            f"INSTRUMENT-DEAD the probe never saw {name} open {sibling} in its "
            "installed copy -- a clean cache here proves nothing"
        )
        return 1

    s_name, s_prefix = REQUIRED_SCRIPT_PROOF
    if not any(p.startswith(s_prefix) for p in script_opened.get(s_name, set())):
        print(
            f"INSTRUMENT-DEAD the script probe never saw {s_name} open anything under "
            f"{s_prefix} in its installed copy -- a clean cache here proves nothing"
        )
        return 1

    for plugin_name in sorted(opened):
        siblings = sorted(p for p in opened[plugin_name] if not p.startswith("hooks/"))
        if args.verbose and siblings:
            print(f"  {plugin_name} loaded siblings: {', '.join(siblings)}")

    for failure in failures:
        print(f"FAIL {failure}")
    if failures:
        print(
            f"{len(failures)} failure(s) across {len(plugins)} plugin(s), {probes} probe(s)"
        )
        return 1
    print(
        f"ok  {probes} hook command(s) across {len(plugins)} installed copies wrote "
        f"no bytecode (probe proven live: {name} opened {sibling})"
    )
    print(
        f"ok  {invocation_count} skill/command/workflow script invocation(s) carry -B, quote the plugin root and "
        f"are permitted by their allowed-tools; {script_runs} script run(s) wrote no bytecode "
        f"(probe proven live: {s_name} opened {s_prefix}...)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
