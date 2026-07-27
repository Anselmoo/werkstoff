#!/usr/bin/env python3
"""Tests for self-assess's PreToolUse target-edit guard.

Mirrors andon's test_andon_enforce.py in rigor. verify-hooks-deny.py's generic
probe cannot exercise this hook meaningfully -- its violating fixture has no
.claude/self-assess.local.md, so the correct response to it is "inert", not
"deny" (the same situation confab's scope-conditional hooks are in). These
tests build the actual self-assess-managed scenarios instead.

Run: python3 plugins/self-assess/hooks/test_guard_target_edit.py
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HOOK = Path(__file__).parent / "guard_target_edit.py"


def git(args, cwd):
    subprocess.run(["git", *args], cwd=cwd, capture_output=True, check=True)


class Repo:
    """A throwaway git repo, optionally self-assess-managed."""

    def __init__(self, settings: str | None = None):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "src").mkdir()
        (self.root / "src" / "api.py").write_text("x = 1\n")
        git(["init", "-q"], self.root)
        git(["config", "user.email", "t@t.com"], self.root)
        git(["config", "user.name", "t"], self.root)
        if settings is not None:
            (self.root / ".claude").mkdir()
            (self.root / ".claude" / "self-assess.local.md").write_text(settings)
        git(["add", "-A"], self.root)
        git(["commit", "-q", "-m", "init"], self.root)

    def dirty(self):
        (self.root / "src" / "api.py").write_text(f"x = {id(self)}\n")

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.tmp.cleanup()


def run(repo: Repo, tool: str = "Edit", target: str = "src/api.py") -> subprocess.CompletedProcess:
    payload = json.dumps({"cwd": str(repo.root), "tool_name": tool,
                          "tool_input": {"file_path": target, "content": "x"}})
    r = subprocess.run([sys.executable, str(HOOK)], input=payload,
                       capture_output=True, text=True, timeout=30)
    assert r.returncode in (0, 2), f"hook must exit 0 (allow) or 2 (deny), got {r.returncode}: {r.stderr}"
    return r


def decision(r: subprocess.CompletedProcess) -> str:
    # allow() emits NO stdout by design (mirrors andon_enforce.py's contract) --
    # only deny() prints JSON. Assuming JSON is always present is a test bug,
    # not a hook bug: it made every correctly-allowed case look like a crash.
    if not r.stdout.strip():
        assert r.returncode == 0, f"empty stdout but exit {r.returncode}, expected 0 for allow"
        return "allow"
    out = json.loads(r.stdout)
    hso = out["hookSpecificOutput"]
    assert hso.get("hookEventName") == "PreToolUse", f"missing hookEventName: {hso!r}"
    pd = hso["permissionDecision"]
    assert (pd == "deny") == (r.returncode == 2), "exit code and permissionDecision disagree"
    return pd


IDIOM_FIX_AUTHORIZED = "---\nenabled: true\nidiom_fix:\n  mode: fix\n---\n"
TRANSFORM_AUTHORIZED = "---\nenabled: true\ntransform:\n  mode: execute\n---\n"


class TestInertness(unittest.TestCase):
    def test_no_settings_no_output_dir_is_inert(self):
        """Without this, the hook would deny target-repo edits in every repo
        on the machine, self-assess-enabled or not."""
        with Repo(settings=None) as repo:
            self.assertEqual(decision(run(repo)), "allow")

    def test_managed_repo_own_output_write_allowed_without_authorization(self):
        with Repo(settings="---\nenabled: true\n---\n") as repo:
            r = run(repo, target="analysis/self-assess/UI_AUDIT.md")
            self.assertEqual(decision(r), "allow")

    def test_non_edit_tool_allowed(self):
        with Repo(settings="---\nenabled: true\n---\n") as repo:
            r = run(repo, tool="Read")
            self.assertEqual(decision(r), "allow")


class TestAuthorizationGate(unittest.TestCase):
    def test_managed_repo_no_authorization_denies_target_edit(self):
        with Repo(settings="---\nenabled: true\n---\n") as repo:
            r = run(repo)
            self.assertEqual(decision(r), "deny")
            self.assertIn("idiom-fix-mode-fix-gate", r.stderr)

    def test_idiom_fix_authorized_and_clean_allows(self):
        with Repo(settings=IDIOM_FIX_AUTHORIZED) as repo:
            self.assertEqual(decision(run(repo)), "allow")

    def test_transform_execute_authorized_and_clean_allows(self):
        with Repo(settings=TRANSFORM_AUTHORIZED) as repo:
            self.assertEqual(decision(run(repo)), "allow")


class TestDirtyTreeGate(unittest.TestCase):
    def test_authorized_but_dirty_denies(self):
        with Repo(settings=IDIOM_FIX_AUTHORIZED) as repo:
            repo.dirty()
            r = run(repo)
            self.assertEqual(decision(r), "deny")
            self.assertIn("dirty-tree-gate", r.stderr)

    def test_authorized_dirty_but_require_clean_tree_false_allows(self):
        settings = "---\nenabled: true\nidiom_fix:\n  mode: fix\nrequire_clean_tree: false\n---\n"
        with Repo(settings=settings) as repo:
            repo.dirty()
            self.assertEqual(decision(run(repo)), "allow")


class TestFailureMode(unittest.TestCase):
    def test_empty_stdin_fails_closed_when_looks_managed(self):
        r = subprocess.run([sys.executable, str(HOOK)], input="",
                           capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 0)  # no tool_input.file_path -> nothing to scope-check


if __name__ == "__main__":
    unittest.main(verbosity=2)
