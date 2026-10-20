#!/usr/bin/env python3
"""The cupertino guard's Python floor (#123): below it, an active repo is DENIED, not crashed open.

Under 3.9 the guard used to raise TypeError at import (`Exception | None`), exit 1, and
Claude Code treats exit 1 as non-blocking -- every call allowed. These cases run the real
hook under every interpreter older than MIN_PYTHON found on PATH (python3.9, python3.10,
/usr/bin/python3) and skip by name when there is none -- unless REQUIRE_OLD_PYTHON=1, as
CI sets it, where finding none is a failure: a skipped case cannot tell a fix from no test.
The sabotage case lowers the floor in a copy of the guard and requires the old interpreter
to ALLOW: proof that the version check, not some other failure, is what denies.

Usage: python3 plugins/cupertino/hooks/test_pretooluse_guard.py
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

GUARD = Path(__file__).resolve().parent / "pretooluse_guard.py"
ALLOW, DENY = 0, 2
FLOOR = (3, 11)
failures = 0


def check(name: str, got: int, want: int, detail: str = "") -> None:
    global failures
    ok = got == want
    failures += not ok
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + ("" if ok else f" (exit {got}, want {want}): {detail[-300:]}"))


def run(python: str, guard: Path, cwd: Path) -> subprocess.CompletedProcess:
    payload = {"cwd": str(cwd), "tool_name": "Bash", "tool_input": {"command": "ls"}}
    env = {"PATH": "/usr/bin:/bin", "CLAUDE_PLUGIN_ROOT": str(GUARD.parent.parent)}
    return subprocess.run([python, "-B", str(guard)], input=json.dumps(payload),
                          capture_output=True, text=True, timeout=30, env=env)


def old_interpreters() -> list[str]:
    found = []
    for name in ("python3.9", "python3.10", "/usr/bin/python3"):
        path = shutil.which(name)
        if not path or path in found:
            continue
        r = subprocess.run([path, "-c", f"import sys; print(sys.version_info[:2] < {FLOOR!r})"],
                           capture_output=True, text=True)
        if r.stdout.strip() == "True":
            found.append(path)
    return found


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        active, inert = Path(tmp) / "active", Path(tmp) / "inert"
        (active / ".cupertino").mkdir(parents=True)
        inert.mkdir()

        r = run(sys.executable, GUARD, active)
        check(f"supported python ({sys.version.split()[0]}), active repo -> ALLOW", r.returncode, ALLOW, r.stderr)

        olds = old_interpreters()
        if not olds:
            if os.environ.get("REQUIRE_OLD_PYTHON") == "1":
                check("REQUIRE_OLD_PYTHON=1 but no python3 older than 3.11 on PATH", 1, 0)
            else:
                print("  skip below-the-floor cases: no python3 older than 3.11 on PATH")
        sabotaged = Path(tmp) / "pretooluse_guard.py"
        sabotaged.write_text(GUARD.read_text().replace("MIN_PYTHON = (3, 11)", "MIN_PYTHON = (3, 0)"))
        for py in olds:
            r = run(py, GUARD, active)
            check(f"{py}, active repo -> DENY", r.returncode, DENY, r.stderr)
            check("  ...and the denial names the floor",
                  ALLOW if "Python >= 3.11" in r.stderr else DENY, ALLOW, r.stderr)
            r = run(py, GUARD, inert)
            check(f"{py}, repo without .cupertino/ -> ALLOW (inert first)", r.returncode, ALLOW, r.stderr)
            r = run(py, sabotaged, active)
            check(f"{py}, sabotage: floor lowered -> ALLOW (the version check is what denies)",
                  r.returncode, ALLOW, r.stderr)

    print(f"\ncupertino guard floor: {'passed' if not failures else f'FAILED ({failures})'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
