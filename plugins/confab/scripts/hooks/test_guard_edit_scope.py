#!/usr/bin/env python3
"""Tests for confab's PreToolUse edit-scope guard.

Mirrors self-assess's hooks/test_guard_target_edit.py in rigor and
structure. verify-hooks-deny.py's generic probe can't exercise this hook's
scope-enforcement branches -- its violating fixture only covers the
wrong-target-file case. These tests build every other scenario directly:
inertness, consumed-scope reuse, and domain/category fixability. This is
the dedicated subprocess test issue #24 itself named as missing.

Run: python3 plugins/confab/scripts/hooks/test_guard_edit_scope.py
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HOOK = Path(__file__).parent / "guard_edit_scope.py"

FIXABLE_SCOPE = {
    "allowedFile": "src/correct_file.py",
    "category": "hallucinated-dependency",
    "consumed": False,
    "domain": "dependency_audit",
    "findingId": "F1",
    "openedAt": 1785183063.0,
}


class Repo:
    """A throwaway repo, optionally with an active confab remediation scope."""

    def __init__(self, scope: dict | None = None, *, confab_dir: bool = True):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "src").mkdir()
        (self.root / "src" / "correct_file.py").write_text("x = 1\n")
        (self.root / "src" / "api.py").write_text("y = 2\n")
        if confab_dir or scope is not None:
            analysis = self.root / "analysis" / "confab"
            analysis.mkdir(parents=True)
            if scope is not None:
                (analysis / "remediation_scope.json").write_text(json.dumps(scope))

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.tmp.cleanup()


def run(repo: Repo, target: str, tool: str = "Edit") -> subprocess.CompletedProcess:
    payload = json.dumps({"cwd": str(repo.root), "tool_name": tool,
                          "tool_input": {"file_path": target, "content": "x"}})
    r = subprocess.run([sys.executable, str(HOOK)], input=payload,
                       capture_output=True, text=True, timeout=30)
    assert r.returncode in (0, 2), f"hook must exit 0 (allow) or 2 (deny), got {r.returncode}: {r.stderr}"
    return r


def decision(r: subprocess.CompletedProcess) -> str:
    # allow() emits NO stdout by design -- only deny() prints JSON. Assuming
    # JSON is always present is a test bug, not a hook bug: it made every
    # correctly-allowed case look like a crash.
    if not r.stdout.strip():
        assert r.returncode == 0, f"empty stdout but exit {r.returncode}, expected 0 for allow"
        return "allow"
    out = json.loads(r.stdout)
    hso = out["hookSpecificOutput"]
    assert hso.get("hookEventName") == "PreToolUse", f"missing hookEventName: {hso!r}"
    pd = hso["permissionDecision"]
    assert (pd == "deny") == (r.returncode == 2), "exit code and permissionDecision disagree"
    return pd


class TestInertness(unittest.TestCase):
    def test_no_confab_dir_is_inert(self):
        """Without this, the hook would deny target-repo edits in every
        repo on the machine, confab-enabled or not."""
        with Repo(confab_dir=False) as repo:
            self.assertEqual(decision(run(repo, "src/api.py")), "allow")

    def test_confab_dir_but_no_scope_is_inert(self):
        with Repo(scope=None) as repo:
            self.assertEqual(decision(run(repo, "src/api.py")), "allow")

    def test_non_edit_tool_allowed(self):
        with Repo(scope=FIXABLE_SCOPE) as repo:
            self.assertEqual(decision(run(repo, "src/api.py", tool="Read")), "allow")


class TestScopeEnforcement(unittest.TestCase):
    def test_wrong_target_file_denies(self):
        with Repo(scope=FIXABLE_SCOPE) as repo:
            r = run(repo, "src/api.py")
            self.assertEqual(decision(r), "deny")
            self.assertIn("remediator-one-fix-per-finding", r.stderr)

    def test_matching_target_fixable_domain_allows(self):
        with Repo(scope=FIXABLE_SCOPE) as repo:
            self.assertEqual(decision(run(repo, "src/correct_file.py")), "allow")

    def test_second_edit_after_consumed_denies(self):
        scope = {**FIXABLE_SCOPE, "consumed": True}
        with Repo(scope=scope) as repo:
            r = run(repo, "src/correct_file.py")
            self.assertEqual(decision(r), "deny")
            self.assertIn("remediator-one-fix-per-finding", r.stderr)

    def test_non_fixable_domain_denies(self):
        scope = {**FIXABLE_SCOPE, "domain": "assertion_audit", "category": "x"}
        with Repo(scope=scope) as repo:
            r = run(repo, "src/correct_file.py")
            self.assertEqual(decision(r), "deny")


class TestFailureMode(unittest.TestCase):
    def test_missing_file_path_denies_when_scope_active(self):
        with Repo(scope=FIXABLE_SCOPE) as repo:
            payload = json.dumps({"cwd": str(repo.root), "tool_name": "Edit", "tool_input": {}})
            r = subprocess.run([sys.executable, str(HOOK)], input=payload,
                               capture_output=True, text=True, timeout=30)
            self.assertEqual(r.returncode, 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
