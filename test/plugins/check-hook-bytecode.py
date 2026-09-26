#!/usr/bin/env python3
"""A plugin hook must not write bytecode into the installed copy (#88).

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

Usage:
    python3 test/plugins/check-hook-bytecode.py [--plugins-root plugins] [-v]

Exit 0 when no copy gained bytecode and the probe is proven live; 1 otherwise.
"""

from __future__ import annotations

import argparse
import json
import os
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

    failures: list[str] = []
    opened: dict[str, set[str]] = {}
    probes = 0

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

    name, sibling = REQUIRED_PROOF
    if sibling not in opened.get(name, set()):
        print(
            f"INSTRUMENT-DEAD the probe never saw {name} open {sibling} in its "
            "installed copy -- a clean cache here proves nothing"
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
    return 0


if __name__ == "__main__":
    sys.exit(main())
