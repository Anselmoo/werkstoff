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

Usage:
    python3 test/plugins/lint-python-floor.py [--plugins-root plugins] [--selftest]

Exit 0 clean, 1 on a finding, 2 when the instrument cannot run.
"""

from __future__ import annotations

import argparse
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
    findings = floor_mismatches(plugins_root, floor)
    if not declared_floors(plugins_root):
        raise InstrumentError(f"no MIN_PYTHON found under {plugins_root}: the scan is dead")
    eol = eol_finding(floor, rrt)
    if eol:
        findings.append(f"floor {floor[0]}.{floor[1]} is end-of-life per rrt eol -- raise it")
    return findings


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
        (root / "p" / "hooks" / "g.py").write_text("MIN_PYTHON = (3, 11)\n")
        (root / "p" / "scripts" / "fixtures" / "f.py").write_text("MIN_PYTHON = (3, 9)\n")
        check("matching floor is clean", lint(root, (3, 11), rrt) == [])
        (root / "p" / "scripts" / "s.py").write_text("MIN_PYTHON = (3, 10)\n")
        check("a drifted MIN_PYTHON is a finding", len(floor_mismatches(root, (3, 11))) == 1)
        check("fixtures are not scanned", all("fixtures" not in str(p) for p, _ in declared_floors(root)))
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
    print(f"{'ok ' if not findings else ''}{n} MIN_PYTHON declaration(s); floor "
          f"{HOOK_PYTHON_FLOOR[0]}.{HOOK_PYTHON_FLOOR[1]}: {len(findings)} finding(s)")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
