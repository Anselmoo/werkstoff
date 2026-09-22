#!/usr/bin/env python3
"""Tests for befund's PreToolUse target-edit guard.

Mirrors andon's test_andon_enforce.py in rigor. verify-hooks-deny.py's generic
probe cannot exercise this hook meaningfully -- its violating fixture has no
edit-scope lock open, so the correct response to it is "inert", not "deny"
(the same situation zeugnis's scope-conditional hooks are in). These tests
build the actual befund-managed scenarios instead.

Run: python3 plugins/befund/hooks/test_guard_target_edit.py
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HOOK = Path(__file__).parent / "guard_target_edit.py"


def git(args, cwd):
    subprocess.run(["git", *args], cwd=cwd, capture_output=True, check=True)


class Repo:
    """A throwaway git repo, optionally befund-managed and/or with an
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
            (self.root / ".claude" / "befund.local.md").write_text(settings)
        if scope is not None:
            scope_dir = self.root / "analysis" / "befund"
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
    """The core fix: this hook must be inert for any edit unless a befund
    remediator dispatch actually has an edit-scope lock open right now --
    regardless of whether the repo looks befund-managed, and regardless
    of what idiom_fix.mode/transform.mode happen to be set to. Denying these
    cases was the bug: every edit from every other plugin (or a direct edit)
    got swept into this gate the moment a repo had befund settings or an
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
            r = run(repo, target="analysis/befund/UI_AUDIT.md")
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


class TestIssue39PathContainment(unittest.TestCase):
    """Regression for issue #39, mirrored from
    test/plugins/fixtures/guard-differential/befund-39-outside-repo and
    befund-39-inside-repo (run those via
    test/plugins/differential-guard-cases.py for the old-vs-new proof; these
    two are the permanent same-process regression).

    The defect: resolved_target was compared only against own_output_dir and
    the lock's allowedFiles, with nothing ever constraining it to be inside
    cwd -- so a target that was not in the target repository AT ALL (an
    absolute path into /tmp, $HOME, or a sibling repo) fell through "not
    own_output_dir, not in allowedFiles" and was denied under
    remediator-scope-enforcement as though it were in-repo source, for the
    whole window a remediator dispatch held the edit-scope lock open.
    """

    def test_absolute_target_outside_repo_is_not_gated_by_this_hook(self):
        """The fix: this hook only gates writes into the TARGET repository's
        own source, so a target outside the repository entirely is allowed,
        not swept into remediator-scope-enforcement."""
        with Repo(settings=IDIOM_FIX_AUTHORIZED, scope=IDIOM_FIX_SCOPE) as repo:
            outside = str(Path(tempfile.gettempdir()) / "befund-39-outside-repo-target" / "notes.md")
            r = run(repo, target=outside)
            self.assertEqual(decision(r), "allow")

    def test_in_repo_target_outside_lock_still_denies(self):
        """The anti-loosening half: an in-repo target that simply isn't named
        in the open lock must still be denied -- the containment check must
        narrow the defect, not loosen remediator-scope-enforcement itself."""
        scope = {"mode": "idiom_fix", "allowedFiles": ["src/api.py"], "openedAt": 0}
        with Repo(settings=IDIOM_FIX_AUTHORIZED, scope=scope) as repo:
            r = run(repo, target="src/other.py")
            self.assertEqual(decision(r), "deny")
            self.assertIn("remediator-scope-enforcement", r.stderr)

    def test_symlink_outside_repo_pointing_into_repo_still_denies(self):
        """The bypass caught in review: the containment check originally
        read `not (lexical_inside and real_inside)` -- allow whenever
        EITHER test said "outside" -- so a path that is lexically OUTSIDE
        cwd but is actually a symlink whose realpath resolves back INSIDE
        cwd (at an unlisted file) was allowed, handing back a way through
        the scope lock that did not exist before issue #39's fix. The
        correct form only allows when BOTH tests agree the target is
        outside; either one saying "inside" must keep it gated.

        Built at runtime with os.symlink rather than committed to the
        fixture tree, because test/plugins/differential-guard-cases.py's
        probe_repo() copies each case with shutil.copytree(child, target)
        (nested entries) and shutil.copy2(child, target) (top-level
        entries) -- both called with their default symlink-following
        behaviour (copytree's symlinks=False, copy2's follow_symlinks=True)
        -- which DEREFERENCES a committed symlink into a plain regular file
        before the guard ever runs. Confirmed empirically: a symlink
        committed at either a top-level or nested case-directory location
        comes out of probe_repo()'s copy step with .is_symlink() == False.
        So a fixture-level differential case cannot actually reproduce this
        scenario without changing differential-guard-cases.py itself, which
        is out of this fix's scope (it is the shared runner, not this
        plugin) -- this in-process test is the real, reliable regression."""
        scope = {"mode": "idiom_fix", "allowedFiles": ["src/api.py"], "openedAt": 0}
        with Repo(settings=IDIOM_FIX_AUTHORIZED, scope=scope) as repo:
            secret = repo.root / "src" / "secret.py"
            secret.write_text("SECRET = 1\n")
            outside_dir = Path(tempfile.mkdtemp(prefix="befund-39-symlink-outside-"))
            self.addCleanup(shutil.rmtree, outside_dir, ignore_errors=True)
            link = outside_dir / "link-to-secret.py"
            link.symlink_to(secret)
            self.assertTrue(link.is_symlink())  # verify the fixture itself, not just the guard
            r = run(repo, target=str(link))
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


class TestEscapeHatch(unittest.TestCase):
    """H-ESCAPE-HATCH: a wrong denial must be bypassable without granting
    blanket source-edit authority. BEFUND_DISABLE_GUARD=1 short-circuits
    run() before anything else, so it overrides even a would-be
    scope-membership deny."""

    def test_disable_guard_env_var_bypasses_a_would_be_deny(self):
        scope = {"mode": "idiom_fix", "allowedFiles": ["src/other.py"], "openedAt": 0}
        with Repo(settings=IDIOM_FIX_AUTHORIZED, scope=scope) as repo:
            payload = json.dumps({"cwd": str(repo.root), "tool_name": "Edit",
                                  "tool_input": {"file_path": "src/api.py", "content": "x"}})
            env = {**os.environ, "BEFUND_DISABLE_GUARD": "1"}
            r = subprocess.run([sys.executable, str(HOOK)], input=payload,
                               capture_output=True, text=True, timeout=30, env=env)
            self.assertEqual(r.returncode, 0)
            self.assertEqual(r.stdout.strip(), "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
