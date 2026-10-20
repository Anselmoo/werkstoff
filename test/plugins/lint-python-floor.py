#!/usr/bin/env python3
"""Every plugin script and hook declares one Python floor, and rrt says it is supported.

A hook runs under whatever `python3` the user's machine has. One that cannot import
exits 1, which Claude Code treats as non-blocking: it ALLOWS every call, silently.
zeugnis's Bash guard did exactly that under 3.9 (`str | None` in a signature). So the
floor is a security property, and two things can rot it:

- a script states its own `MIN_PYTHON` that drifts from the others (install_waves.py
  and waves_state.py said 3.10 while every other one said 3.11);
- the floor itself reaches end of life with nobody looking.

The first is checked here by reading every `MIN_PYTHON = (x, y)` under
`plugins/*/hooks/` and `plugins/*/scripts/` (fixtures excluded). The second is
delegated to `rrt eol`: this script writes a throwaway `pyproject.toml` whose
`requires-python` is the floor and runs `rrt eol --language python --project-only`
against it, so the EOL dates are rrt's bundled data, never a table kept here. rrt
missing is exit 2, never a pass.

Declaring a floor is not enforcing it (#123). So every script a `hooks/hooks.json`
registers -- read from the commands, since zeugnis's live in `scripts/hooks/` -- must
also carry, by AST: `from __future__ import annotations` (or the module crashes before
the check can run), a module-level `MIN_PYTHON`, and an `if sys.version_info <
MIN_PYTHON:` whose body calls something (`pass` there is a guard-shaped no-op). A
registered script that is missing, a hooks.json that does not parse, or no registered
hook at all is reported, never skipped.

Usage:
    python3 test/plugins/lint-python-floor.py [--plugins-root plugins] [--selftest]

Exit 0 clean, 1 on a finding, 2 when the instrument cannot run.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HOOK_PYTHON_FLOOR = (3, 11)
WARN_DAYS = 365

REPO = Path(__file__).resolve().parents[2]
NOT_SHIPPED = {"fixtures", "testdata", "__pycache__", "node_modules"}
MIN_PYTHON = re.compile(r"^MIN_PYTHON\s*=\s*\(\s*(\d+)\s*,\s*(\d+)\s*\)", re.MULTILINE)


class InstrumentError(Exception):
    pass


HOOK_SCRIPT = re.compile(r"\$\{CLAUDE_PLUGIN_ROOT\}/([A-Za-z0-9_./-]+?\.py)")


def registered_hooks(plugins_root: Path) -> tuple[list[Path], list[str]]:
    """Scripts every hooks.json registers as a command hook, and the findings met reading them."""
    scripts, findings = [], []
    for hj in sorted(plugins_root.glob("*/hooks/hooks.json")):
        plugin = hj.parent.parent
        try:
            events = json.loads(hj.read_text(encoding="utf-8")).get("hooks", {})
        except (OSError, ValueError) as e:
            findings.append(f"{hj.relative_to(plugins_root.parent)}: does not parse ({e})")
            continue
        for entries in events.values():
            for entry in entries:
                for hook in entry.get("hooks", []):
                    if hook.get("type") != "command":
                        continue
                    for rel in HOOK_SCRIPT.findall(hook.get("command", "")):
                        path = plugin / rel
                        if path not in scripts:
                            scripts.append(path)
    return scripts, findings


def _is_floor_check(test: ast.expr) -> bool:
    return (isinstance(test, ast.Compare) and len(test.ops) == 1 and isinstance(test.ops[0], ast.Lt)
            and ast.unparse(test.left) == "sys.version_info"
            and ast.unparse(test.comparators[0]) == "MIN_PYTHON")


def unguarded_hooks(plugins_root: Path) -> list[str]:
    scripts, findings = registered_hooks(plugins_root)
    if not scripts and not findings:
        raise InstrumentError(f"no hooks.json under {plugins_root} registers a script: the scan is dead")
    for path in scripts:
        name = path.relative_to(plugins_root.parent)
        if not path.is_file():
            findings.append(f"{name}: registered in hooks.json but does not exist")
            continue
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        if not any(isinstance(n, ast.ImportFrom) and n.module == "__future__"
                   and any(a.name == "annotations" for a in n.names) for n in tree.body):
            findings.append(f"{name}: no `from __future__ import annotations` -- may crash (exit 1 = allow) "
                            "before the floor check runs")
        if not MIN_PYTHON.search(source):
            findings.append(f"{name}: no module-level MIN_PYTHON")
        checks = [n for n in ast.walk(tree) if isinstance(n, ast.If) and _is_floor_check(n.test)]
        if not checks:
            findings.append(f"{name}: no `if sys.version_info < MIN_PYTHON:` -- below the floor it runs untested")
        elif not any(isinstance(m, ast.Call) for c in checks for stmt in c.body for m in ast.walk(stmt)):
            findings.append(f"{name}: `if sys.version_info < MIN_PYTHON:` calls nothing -- a guard-shaped no-op")
    return findings


def declared_floors(plugins_root: Path) -> list[tuple[Path, tuple[int, int]]]:
    found = []
    for path in sorted(plugins_root.glob("*/*/**/*.py")):
        rel = path.relative_to(plugins_root).parts
        if rel[1] not in {"hooks", "scripts"} or NOT_SHIPPED.intersection(rel):
            continue
        for m in MIN_PYTHON.finditer(path.read_text(encoding="utf-8")):
            found.append((path, (int(m.group(1)), int(m.group(2)))))
    return found


def floor_mismatches(plugins_root: Path, floor: tuple[int, int]) -> list[str]:
    return [
        f"{path.relative_to(plugins_root.parent)}: MIN_PYTHON = {got}, floor is {floor}"
        for path, got in declared_floors(plugins_root)
        if got != floor
    ]


def eol_finding(floor: tuple[int, int], rrt: str | None) -> str | None:
    """None when rrt says the floor is supported; the rrt report otherwise."""
    if rrt is None:
        raise InstrumentError("rrt not on PATH (uv tool install 'repo-release-tools>=1.18.0')")
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "pyproject.toml").write_text(
            '[project]\nname = "python-floor-probe"\nversion = "0"\n'
            f'requires-python = ">={floor[0]}.{floor[1]}"\n',
            encoding="utf-8",
        )
        r = subprocess.run(
            [rrt, "eol", "--language", "python", "--project-only",
             "--warn-days", str(WARN_DAYS), "--error-days", "0"],
            cwd=tmp, capture_output=True, text=True, timeout=60,
        )
    report = (r.stdout + r.stderr).strip()
    if f"{floor[0]}.{floor[1]}" not in report:
        raise InstrumentError(f"rrt eol never reported on {floor[0]}.{floor[1]}:\n{report}")
    print(report)
    return report if r.returncode != 0 else None


def lint(plugins_root: Path, floor: tuple[int, int], rrt: str | None) -> list[str]:
    findings = floor_mismatches(plugins_root, floor) + unguarded_hooks(plugins_root)
    if not declared_floors(plugins_root):
        raise InstrumentError(f"no MIN_PYTHON found under {plugins_root}: the scan is dead")
    eol = eol_finding(floor, rrt)
    if eol:
        findings.append(f"floor {floor[0]}.{floor[1]} is end-of-life per rrt eol -- raise it")
    return findings


_FLOOR_IF = "if sys.version_info < MIN_PYTHON:\n    deny()\n"
GOOD_HOOK = (
    "from __future__ import annotations\n\nimport sys\n\nMIN_PYTHON = (3, 11)\n\n\n"
    "def deny():\n    sys.exit(2)\n\n\n" + _FLOOR_IF
)


def _register(plugin: Path, rel: str) -> None:
    (plugin / "hooks").mkdir(parents=True, exist_ok=True)
    command = f'python3 -B "${{CLAUDE_PLUGIN_ROOT}}/{rel}"'
    (plugin / "hooks" / "hooks.json").write_text(json.dumps(
        {"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": command}]}]}}))


def selftest(rrt: str | None) -> int:
    failures = 0

    def check(name: str, ok: bool) -> None:
        nonlocal failures
        print(f"  {'ok  ' if ok else 'FAIL'} {name}")
        failures += not ok

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "plugins"
        (root / "p" / "hooks").mkdir(parents=True)
        (root / "p" / "scripts" / "fixtures").mkdir(parents=True)
        (root / "p" / "hooks" / "g.py").write_text(GOOD_HOOK)
        _register(root / "p", "hooks/g.py")
        (root / "p" / "scripts" / "fixtures" / "f.py").write_text("MIN_PYTHON = (3, 9)\n")
        check("matching floor is clean", lint(root, (3, 11), rrt) == [])
        (root / "p" / "scripts" / "s.py").write_text("MIN_PYTHON = (3, 10)\n")
        check("a drifted MIN_PYTHON is a finding", len(floor_mismatches(root, (3, 11))) == 1)
        check("fixtures are not scanned", all("fixtures" not in str(p) for p, _ in declared_floors(root)))
    for label, source, rel in [
        ("a hook with no floor check is a finding", GOOD_HOOK.replace(_FLOOR_IF, ""), "hooks/g.py"),
        ("`if ...: pass` is a finding", GOOD_HOOK.replace("    deny()", "    pass"), "hooks/g.py"),
        ("a hook without __future__ is a finding", GOOD_HOOK.replace("from __future__ import annotations\n", ""),
         "hooks/g.py"),
        ("a hook without MIN_PYTHON is a finding", GOOD_HOOK.replace("MIN_PYTHON = (3, 11)\n", ""), "hooks/g.py"),
        ("a scripts/hooks/ registration (zeugnis's layout) is checked", GOOD_HOOK.replace(_FLOOR_IF, ""),
         "scripts/hooks/g.py"),
    ]:
        with tempfile.TemporaryDirectory() as tmp:
            plugin = Path(tmp) / "plugins" / "p"
            (plugin / rel).parent.mkdir(parents=True)
            (plugin / rel).write_text(source)
            _register(plugin, rel)
            check(label, len(unguarded_hooks(plugin.parent)) == 1)
    with tempfile.TemporaryDirectory() as tmp:
        plugin = Path(tmp) / "plugins" / "p"
        (plugin / "hooks").mkdir(parents=True)
        _register(plugin, "hooks/missing.py")
        check("a registered script that does not exist is a finding",
              any("does not exist" in f for f in unguarded_hooks(plugin.parent)))
        (plugin / "hooks" / "hooks.json").write_text("{not json")
        check("an unparseable hooks.json is a finding",
              any("does not parse" in f for f in unguarded_hooks(plugin.parent)))
        (plugin / "hooks" / "hooks.json").unlink()
        try:
            unguarded_hooks(plugin.parent)
            check("no registered hook at all raises", False)
        except InstrumentError:
            check("no registered hook at all raises", True)
    # Sabotage: lower the floor to an EOL cycle and the rrt half must bite.
    check("an EOL floor (3.9) is a finding", eol_finding((3, 9), rrt) is not None)
    try:
        eol_finding((3, 11), None)
        check("missing rrt raises", False)
    except InstrumentError:
        check("missing rrt raises", True)
    print(f"\nlint-python-floor selftest {'passed' if not failures else f'FAILED ({failures})'}")
    return 1 if failures else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--plugins-root", type=Path, default=REPO / "plugins")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    rrt = shutil.which("rrt")
    try:
        if args.selftest:
            return selftest(rrt)
        findings = lint(args.plugins_root, HOOK_PYTHON_FLOOR, rrt)
    except InstrumentError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    for f in findings:
        print(f"FAIL {f}")
    n = len(declared_floors(args.plugins_root))
    h = len(registered_hooks(args.plugins_root)[0])
    print(f"{'ok ' if not findings else ''}{n} MIN_PYTHON declaration(s), {h} registered hook(s); floor "
          f"{HOOK_PYTHON_FLOOR[0]}.{HOOK_PYTHON_FLOOR[1]}: {len(findings)} finding(s)")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
