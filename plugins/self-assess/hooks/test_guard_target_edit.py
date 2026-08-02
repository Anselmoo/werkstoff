#!/usr/bin/env python3
"""Tests for self-assess's PreToolUse target-edit guard.

Mirrors andon's test_andon_enforce.py in rigor. verify-hooks-deny.py's generic
probe cannot exercise this hook meaningfully -- its violating fixture has no
edit-scope lock open, so the correct response to it is "inert", not "deny"
(the same situation confab's scope-conditional hooks are in). These tests
build the actual self-assess-managed scenarios instead.

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
    """A throwaway git repo, optionally self-assess-managed and/or with an
    edit-scope lock open."""

    def __init__(self, settings: str | None = None, scope: dict | None = None):
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
        if scope is not None:
            scope_dir = self.root / "analysis" / "self-assess"
            scope_dir.mkdir(parents=True)
            (scope_dir / "edit_scope.json").write_text(json.dumps(scope))
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
IDIOM_FIX_SCOPE = {"mode": "idiom_fix", "allowedFiles": ["src/api.py"], "openedAt": 0}
TRANSFORM_SCOPE = {"mode": "transform", "allowedFiles": ["src/api.py"], "openedAt": 0}


class TestInertWithoutAnOpenScope(unittest.TestCase):
    """The core fix: this hook must be inert for any edit unless a self-assess
    remediator dispatch actually has an edit-scope lock open right now --
    regardless of whether the repo looks self-assess-managed, and regardless
    of what idiom_fix.mode/transform.mode happen to be set to. Denying these
    cases was the bug: every edit from every other plugin (or a direct edit)
    got swept into this gate the moment a repo had self-assess settings or an
    output dir at all.
    """

    def test_no_settings_no_scope_is_inert(self):
        with Repo(settings=None, scope=None) as repo:
            self.assertEqual(decision(run(repo)), "allow")

    def test_settings_present_but_unauthorized_and_no_scope_open_allows(self):
        with Repo(settings="---\nenabled: true\n---\n", scope=None) as repo:
            self.assertEqual(decision(run(repo)), "allow")

    def test_settings_authorized_but_no_scope_open_allows(self):
        """Even with idiom_fix.mode: fix set, an edit from some OTHER plugin
        or a direct edit -- one that never opened a scope lock -- must not be
        gated by a rule that isn't about it."""
        with Repo(settings=IDIOM_FIX_AUTHORIZED, scope=None) as repo:
            self.assertEqual(decision(run(repo)), "allow")

    def test_non_edit_tool_allowed(self):
        with Repo(settings="---\nenabled: true\n---\n", scope=IDIOM_FIX_SCOPE) as repo:
            r = run(repo, tool="Read")
            self.assertEqual(decision(r), "allow")

    def test_managed_repo_own_output_write_allowed_even_with_scope_open(self):
        with Repo(settings="---\nenabled: true\n---\n", scope=IDIOM_FIX_SCOPE) as repo:
            r = run(repo, target="analysis/self-assess/UI_AUDIT.md")
            self.assertEqual(decision(r), "allow")


class TestScopeFileMembership(unittest.TestCase):
    def test_scope_open_naming_target_and_mode_authorized_allows(self):
        with Repo(settings=IDIOM_FIX_AUTHORIZED, scope=IDIOM_FIX_SCOPE) as repo:
            self.assertEqual(decision(run(repo)), "allow")

    def test_transform_scope_open_naming_target_and_mode_authorized_allows(self):
        with Repo(settings=TRANSFORM_AUTHORIZED, scope=TRANSFORM_SCOPE) as repo:
            self.assertEqual(decision(run(repo)), "allow")

    def test_scope_open_but_target_not_named_denies(self):
        scope = {"mode": "idiom_fix", "allowedFiles": ["src/other.py"], "openedAt": 0}
        with Repo(settings=IDIOM_FIX_AUTHORIZED, scope=scope) as repo:
            r = run(repo, target="src/api.py")
            self.assertEqual(decision(r), "deny")
            self.assertIn("remediator-scope-enforcement", r.stderr)


class TestModeGateStillEnforcedUnderAnOpenScope(unittest.TestCase):
    """Defense in depth: a scope naming the right file is not by itself
    sufficient -- the settings must actually authorize the mode the scope
    claims, in case the scope file is stale or hand-edited."""

    def test_scope_open_but_settings_never_authorized_denies(self):
        with Repo(settings="---\nenabled: true\n---\n", scope=IDIOM_FIX_SCOPE) as repo:
            r = run(repo)
            self.assertEqual(decision(r), "deny")
            self.assertIn("idiom-fix-mode-fix-gate", r.stderr)

    def test_transform_scope_open_but_settings_never_authorized_denies(self):
        with Repo(settings="---\nenabled: true\n---\n", scope=TRANSFORM_SCOPE) as repo:
            r = run(repo)
            self.assertEqual(decision(r), "deny")
            self.assertIn("transform-execute-gate-transform-mode", r.stderr)


class TestDirtyTreeGate(unittest.TestCase):
    def test_authorized_scope_open_but_dirty_denies(self):
        with Repo(settings=IDIOM_FIX_AUTHORIZED, scope=IDIOM_FIX_SCOPE) as repo:
            repo.dirty()
            r = run(repo)
            self.assertEqual(decision(r), "deny")
            self.assertIn("dirty-tree-gate", r.stderr)

    def test_authorized_scope_open_dirty_but_require_clean_tree_false_allows(self):
        settings = "---\nenabled: true\nidiom_fix:\n  mode: fix\nrequire_clean_tree: false\n---\n"
        with Repo(settings=settings, scope=IDIOM_FIX_SCOPE) as repo:
            repo.dirty()
            self.assertEqual(decision(run(repo)), "allow")


class TestFailureMode(unittest.TestCase):
    def test_empty_stdin_fails_closed_when_looks_managed(self):
        r = subprocess.run([sys.executable, str(HOOK)], input="",
                           capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 0)  # no tool_input.file_path -> nothing to scope-check


if __name__ == "__main__":
    unittest.main(verbosity=2)
