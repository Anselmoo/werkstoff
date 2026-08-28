#!/usr/bin/env python3
"""Gate: takt's guard must evaluate every edit-payload shape, not just the easy one.

verify-hooks-deny.py proves a hook denies *a* violation, and it drives exactly one
payload shape: {"tool_name": "Edit", "tool_input": {"file_path": ...}}. That is the
right contract for a shared harness, but it left a real gap -- takt's first
implementation read only `tool_input["file_path"]`, so a MultiEdit carrying its paths
in an `edits` array produced an empty target, matched nothing, and was ALLOWED in a
repository that had opted in. A fail-closed guard that silently allows is the exact
"looks correct and does nothing" shape CLAUDE.md catalogues.

This file pins the payload shapes that harness cannot express. It is deliberately
narrow: it tests takt's guard against the checked-in fixture, and nothing else.

Usage:  verify-takt-payload-shapes.py
Exit:   0 if every case behaves as specified, 1 otherwise.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
GUARD = REPO / "plugins" / "takt" / "hooks" / "takt_guard.py"
OPTED_IN = REPO / "test" / "plugins" / "fixtures" / "hook-violation-takt"

DENY, ALLOW = 2, 0

# (label, cwd, tool_name, tool_input, env, expected_exit)
CASES = [
    ("MultiEdit, path only in edits[], gated",
     OPTED_IN, "MultiEdit", {"edits": [{"file_path": "src/ui/Panel.tsx"}]}, {}, DENY),
    ("MultiEdit, no determinable path at all -> fail closed",
     OPTED_IN, "MultiEdit", {"edits": [{"old_string": "x", "new_string": "y"}]}, {}, DENY),
    ("MultiEdit, several paths, one of them gated",
     OPTED_IN, "MultiEdit",
     {"edits": [{"file_path": "src/api.py"}, {"file_path": "src/ui/Panel.tsx"}]}, {}, DENY),
    ("MultiEdit, file_paths[] variant, gated",
     OPTED_IN, "MultiEdit", {"file_paths": ["src/ui/Panel.tsx"]}, {}, DENY),
    ("MultiEdit, only ungated paths",
     OPTED_IN, "MultiEdit", {"edits": [{"file_path": "src/api.py"}]}, {}, ALLOW),
    ("MultiEdit, indeterminate, repo not opted in -> inert",
     REPO, "MultiEdit", {"edits": [{"old_string": "x"}]}, {}, ALLOW),
    ("MultiEdit, gated, escape hatch set",
     OPTED_IN, "MultiEdit", {"edits": [{"file_path": "src/ui/Panel.tsx"}]},
     {"TAKT_DISABLE_GUARD": "1"}, ALLOW),
    ("Edit, gated (regression: original behaviour)",
     OPTED_IN, "Edit", {"file_path": "src/ui/Panel.tsx"}, {}, DENY),
    ("Edit, ungated (regression)",
     OPTED_IN, "Edit", {"file_path": "src/api.py"}, {}, ALLOW),
    ("Write, gated via top-level file_path (regression)",
     OPTED_IN, "Write", {"file_path": "src/ui/Panel.tsx"}, {}, DENY),
]


def run(cwd: Path, tool_name: str, tool_input: dict, extra_env: dict) -> int:
    payload = json.dumps({"cwd": str(cwd), "tool_name": tool_name, "tool_input": tool_input})
    env = {**os.environ, **extra_env}
    if "TAKT_DISABLE_GUARD" not in extra_env:
        env.pop("TAKT_DISABLE_GUARD", None)  # never inherit it from the caller
    result = subprocess.run(
        [sys.executable, str(GUARD)], input=payload, capture_output=True, text=True, env=env
    )
    return result.returncode


def main() -> int:
    if not GUARD.is_file():
        print(f"error: guard not found at {GUARD}", file=sys.stderr)
        return 1
    if not (OPTED_IN / ".claude" / "takt.local.md").is_file():
        print(f"error: fixture missing its beat declaration under {OPTED_IN}", file=sys.stderr)
        return 1

    failures = 0
    print(f"{'case':<62}{'want':<7}{'got':<6}verdict")
    print("-" * 86)
    for label, cwd, tool_name, tool_input, extra_env, expected in CASES:
        actual = run(cwd, tool_name, tool_input, extra_env)
        ok = actual == expected
        failures += 0 if ok else 1
        print(f"{label:<62}{expected:<7}{actual:<6}{'ok' if ok else 'FAIL'}")

    print()
    if failures:
        print(f"{failures} case(s) failed. A fail-closed guard that allows is a silent bypass.")
        return 1
    print(f"All {len(CASES)} payload shapes behave as specified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
