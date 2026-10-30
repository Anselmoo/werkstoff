#!/usr/bin/env python3
"""Tests for zeugnis's PreToolUse edit-scope guard.

Mirrors befund's hooks/test_guard_target_edit.py in rigor and
structure. verify-hooks-deny.py's generic probe can't exercise this hook's
scope-enforcement branches -- its violating fixture only covers the
wrong-target-file case. These tests build every other scenario directly:
inertness, consumed-scope reuse, and domain/category fixability. This is
the dedicated subprocess test issue #24 itself named as missing.

Run: python3 plugins/zeugnis/scripts/hooks/test_guard_edit_scope.py
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

FLOOR = (3, 11)
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
    """A throwaway repo, optionally with an active zeugnis remediation scope."""

    def __init__(self, scope: dict | None = None, *, zeugnis_dir: bool = True):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "src").mkdir()
        (self.root / "src" / "correct_file.py").write_text("x = 1\n")
        (self.root / "src" / "api.py").write_text("y = 2\n")
        if zeugnis_dir or scope is not None:
            analysis = self.root / "analysis" / "zeugnis"
            analysis.mkdir(parents=True)
            if scope is not None:
                (analysis / "remediation_scope.json").write_text(json.dumps(scope))

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.tmp.cleanup()


def run(repo: Repo, target: str, tool: str = "Edit",
        env_extra: dict | None = None) -> subprocess.CompletedProcess:
    import os

    payload = json.dumps({"cwd": str(repo.root), "tool_name": tool,
                          "tool_input": {"file_path": target, "content": "x"}})
    env = {**os.environ, **(env_extra or {})}
    r = subprocess.run([sys.executable, str(HOOK)], input=payload,
                       capture_output=True, text=True, timeout=30, env=env)
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
    def test_no_zeugnis_dir_is_inert(self):
        """Without this, the hook would deny target-repo edits in every
        repo on the machine, zeugnis-enabled or not."""
        with Repo(zeugnis_dir=False) as repo:
            self.assertEqual(decision(run(repo, "src/api.py")), "allow")

    def test_zeugnis_dir_but_no_scope_is_inert(self):
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


class TestEscapeHatch(unittest.TestCase):
    """ZEUGNIS_DISABLE_GUARD=1, and what it deliberately does NOT do.

    H-ESCAPE-HATCH: before this, a wrong denial here could only be cleared by
    deleting the remediation lock -- i.e. destroying audit state to make one
    edit. The sibling Bash guard gained the var in PR #95; this one had none.
    """

    def _scope(self, repo):
        return json.loads(
            (repo.root / "analysis" / "zeugnis" / "remediation_scope.json").read_text())

    def test_env_var_bypasses_a_would_be_deny(self):
        with Repo(scope=FIXABLE_SCOPE) as repo:
            # src/api.py is NOT the locked allowedFile, so this denies without it
            self.assertEqual(decision(run(repo, "src/api.py")), "deny")
            r = run(repo, "src/api.py", env_extra={"ZEUGNIS_DISABLE_GUARD": "1"})
            self.assertEqual(decision(r), "allow")

    def test_bypass_does_not_spend_the_one_shot_budget(self):
        """The difference from guard_bash_scope, which writes nothing.

        This hook is the only writer of `consumed: true`. An early return skips
        mark_consumed, so an edit the guard never judged does not count against
        the finding's single authorized fix. Asserted rather than assumed,
        because it is the non-obvious half of the change.
        """
        with Repo(scope=FIXABLE_SCOPE) as repo:
            self.assertFalse(self._scope(repo)["consumed"])
            run(repo, "src/correct_file.py", env_extra={"ZEUGNIS_DISABLE_GUARD": "1"})
            self.assertFalse(
                self._scope(repo)["consumed"],
                "a bypassed edit must not consume the remediation budget")

    def test_unset_is_the_default(self):
        with Repo(scope=FIXABLE_SCOPE) as repo:
            self.assertEqual(decision(run(repo, "src/api.py")), "deny")

    def test_other_values_do_not_bypass(self):
        with Repo(scope=FIXABLE_SCOPE) as repo:
            for v in ("0", "true", "yes", ""):
                r = run(repo, "src/api.py", env_extra={"ZEUGNIS_DISABLE_GUARD": v})
                self.assertEqual(decision(r), "deny", f"value {v!r} must not bypass")


class TestFailureMode(unittest.TestCase):
    def test_missing_file_path_denies_when_scope_active(self):
        with Repo(scope=FIXABLE_SCOPE) as repo:
            payload = json.dumps({"cwd": str(repo.root), "tool_name": "Edit", "tool_input": {}})
            r = subprocess.run([sys.executable, str(HOOK)], input=payload,
                               capture_output=True, text=True, timeout=30)
            self.assertEqual(r.returncode, 2)


def _old_interpreters() -> list[str]:
    """Every python3 older than the guard's floor on PATH (#123)."""
    import shutil

    found: list[str] = []
    for name in ("python3.9", "python3.10", "/usr/bin/python3"):
        path = shutil.which(name)
        if not path or path in found:
            continue
        r = subprocess.run([path, "-c", f"import sys; print(sys.version_info[:2] < {FLOOR!r})"],
                           capture_output=True, text=True)
        if r.stdout.strip() == "True":
            found.append(path)
    return found


class TestPythonFloor(unittest.TestCase):
    """#123: below MIN_PYTHON an active repo is DENIED, never crashed open.

    A hook that cannot import exits 1, which Claude Code treats as non-blocking:
    the call goes through. These run the real guard under every python3 older
    than 3.11 on PATH. The sabotage case lowers the floor in a copy of scripts/
    and requires the same payload to be allowed -- proof that the version check,
    not some other failure, is what denies. No old interpreter is a skip, or a
    failure under REQUIRE_OLD_PYTHON=1 (as CI sets it).
    """

    def setUp(self):
        import os

        self.olds = _old_interpreters()
        if not self.olds:
            if os.environ.get("REQUIRE_OLD_PYTHON") == "1":
                self.fail("REQUIRE_OLD_PYTHON=1 but no python3 older than 3.11 on PATH")
            self.skipTest("no python3 older than 3.11 on PATH")

    def _run(self, python: str, hook: Path, repo: Repo) -> subprocess.CompletedProcess:
        import os

        env = {k: v for k, v in os.environ.items() if k != "ZEUGNIS_DISABLE_GUARD"}
        payload = json.dumps({"cwd": str(repo.root), "tool_name": "Edit",
                              "tool_input": {"file_path": "src/correct_file.py", "content": "x"}})
        return subprocess.run([python, "-B", str(hook)], input=payload,
                              capture_output=True, text=True, timeout=30, env=env)

    def test_below_floor_active_repo_denies_and_names_the_floor(self):
        with Repo(scope=FIXABLE_SCOPE) as repo:
            for py in self.olds:
                r = self._run(py, HOOK, repo)
                self.assertEqual(r.returncode, 2, f"{py}: {r.stderr}")
                self.assertIn("Python >= 3.11", r.stderr, py)

    def test_below_floor_inert_repo_allows(self):
        with Repo(zeugnis_dir=False) as repo:
            for py in self.olds:
                r = self._run(py, HOOK, repo)
                self.assertEqual(r.returncode, 0, f"{py}: {r.stderr}")

    def test_sabotage_floor_lowered_allows(self):
        import shutil

        with tempfile.TemporaryDirectory() as tmp:
            scripts = Path(tmp) / "scripts"
            shutil.copytree(HOOK.parent.parent, scripts,
                            ignore=shutil.ignore_patterns("__pycache__"))
            hook = scripts / "hooks" / HOOK.name
            text = hook.read_text()
            self.assertIn("MIN_PYTHON = (3, 11)", text)
            hook.write_text(text.replace("MIN_PYTHON = (3, 11)", "MIN_PYTHON = (3, 0)"))
            for py in self.olds:
                # A fresh scope per interpreter: an allowed edit spends the
                # one-shot budget, so the next run would be a refused second edit.
                with Repo(scope=FIXABLE_SCOPE) as repo:
                    r = self._run(py, hook, repo)
                    self.assertNotEqual(r.returncode, 2, f"{py}: {r.stderr}")


TEST_SCOPE = {
    "category": "surviving-mutant",
    "consumed": False,
    "domain": "mutation_harden",
    "editBudget": 2,
    "editsUsed": 0,
    "findingId": "lane-pricing",
    "openedAt": 1785183063.0,
    "sourcePaths": ["src"],
    "testRoots": ["tests"],
}
CLI = Path(__file__).parent.parent / "remediation_scope_cli.py"


def scope_on_disk(repo: Repo) -> dict:
    return json.loads((repo.root / "analysis" / "zeugnis" / "remediation_scope.json").read_text())


class TestMutationHardenTestScope(unittest.TestCase):
    """Issue #142: a killing test may be a NEW test file, so this domain's
    lock is a test-path scope -- and it must still deny every source write."""

    def test_new_test_file_allowed_and_spends_budget(self):
        with Repo(TEST_SCOPE) as repo:
            self.assertEqual(decision(run(repo, "tests/test_pricing_boundary.py", tool="Write")), "allow")
            self.assertEqual(scope_on_disk(repo)["editsUsed"], 1)
            self.assertEqual(decision(run(repo, str(repo.root / "tests" / "unit" / "test_x.py"))), "allow")

    def test_source_file_denied(self):
        with Repo(TEST_SCOPE) as repo:
            r = run(repo, "src/correct_file.py")
            self.assertEqual(decision(r), "deny")
            self.assertIn("never by editing the code it survived in", r.stderr)
            self.assertEqual(scope_on_disk(repo)["editsUsed"], 0, "a denied write must not spend budget")

    def test_test_named_file_under_source_denied(self):
        with Repo(TEST_SCOPE) as repo:
            self.assertEqual(decision(run(repo, "src/test_sneaky.py", tool="Write")), "deny")

    def test_collection_config_denied_even_under_test_root(self):
        with Repo(TEST_SCOPE) as repo:
            for target in ("tests/conftest.py", "tests/pytest.ini", "pyproject.toml", "setup.cfg"):
                self.assertEqual(decision(run(repo, target, tool="Write")), "deny", target)

    def test_outside_test_roots_denied(self):
        with Repo(TEST_SCOPE) as repo:
            for target in ("docs/test_x.py", "analysis/zeugnis/mutation/r1/records/x.json",
                           "tests/../src/api.py", "../elsewhere/tests/test_x.py"):
                self.assertEqual(decision(run(repo, target, tool="Write")), "deny", target)

    def test_budget_exhausted_denies(self):
        with Repo({**TEST_SCOPE, "editsUsed": 2}) as repo:
            r = run(repo, "tests/test_more.py", tool="Write")
            self.assertEqual(decision(r), "deny")
            self.assertIn("budget is spent", r.stderr)

    def test_lock_missing_test_roots_denies_not_falls_through(self):
        """Branch on DOMAIN: a mutation_harden lock shaped like the old
        single-file lock must not authorise its allowedFile (a source file)."""
        legacy = {**FIXABLE_SCOPE, "domain": "mutation_harden", "allowedFile": "src/correct_file.py"}
        with Repo(legacy) as repo:
            self.assertEqual(decision(run(repo, "src/correct_file.py")), "deny")
            self.assertEqual(decision(run(repo, "tests/test_x.py", tool="Write")), "deny")

    def test_symlinked_test_root_denied(self):
        with Repo(TEST_SCOPE) as repo:
            (repo.root / "tests").symlink_to(repo.root / "src", target_is_directory=True)
            self.assertEqual(decision(run(repo, "tests/correct_file.py")), "deny")

    def test_cwd_inside_mutation_copy_stays_guarded(self):
        """The copy has no analysis/zeugnis/; the guard walks up to the repo."""
        import os

        with Repo(TEST_SCOPE) as repo:
            copy = repo.root / "analysis" / "zeugnis" / "mutation" / "r1" / "shards" / "core"
            copy.mkdir(parents=True)
            payload = json.dumps({"cwd": str(copy), "tool_name": "Edit",
                                  "tool_input": {"file_path": str(repo.root / "src" / "api.py")}})
            env = {k: v for k, v in os.environ.items() if k != "ZEUGNIS_DISABLE_GUARD"}
            r = subprocess.run([sys.executable, str(HOOK)], input=payload,
                               capture_output=True, text=True, timeout=30, env=env)
            self.assertEqual(decision(r), "deny")


class TestOpenTestsCli(unittest.TestCase):
    def _cli(self, repo: Repo, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(CLI), *args], capture_output=True, text=True, timeout=30)

    def test_single_file_open_refuses_mutation_harden(self):
        with Repo() as repo:
            r = self._cli(repo, "open", str(repo.root), "--finding-id", "m1", "--domain", "mutation_harden",
                          "--category", "surviving-mutant", "--target-file", "src/correct_file.py")
            self.assertEqual(r.returncode, 3, r.stderr)
            self.assertIn("open-tests", r.stderr)

    def test_open_tests_writes_the_test_scope(self):
        with Repo() as repo:
            r = self._cli(repo, "open-tests", str(repo.root), "--lane-id", "lane-1", "--test-root", "tests",
                          "--source-path", "src", "--edit-budget", "3")
            self.assertEqual(r.returncode, 0, r.stderr)
            scope = scope_on_disk(repo)
            self.assertEqual((scope["domain"], scope["testRoots"], scope["sourcePaths"], scope["editBudget"]),
                             ("mutation_harden", ["tests"], ["src"], 3))

    def test_open_tests_refuses_overlap_and_escape(self):
        with Repo() as repo:
            for test_root, source in (("src/tests", "src"), ("tests", "tests/fixtures"), ("../x", "src"),
                                      ("analysis/zeugnis", "src")):
                r = self._cli(repo, "open-tests", str(repo.root), "--lane-id", "l", "--test-root", test_root,
                              "--source-path", source, "--edit-budget", "1")
                self.assertEqual(r.returncode, 4, f"{test_root} vs {source}: {r.stderr}")

    def test_open_tests_refuses_zero_budget(self):
        with Repo() as repo:
            r = self._cli(repo, "open-tests", str(repo.root), "--lane-id", "l", "--test-root", "tests",
                          "--source-path", "src", "--edit-budget", "0")
            self.assertEqual(r.returncode, 4, r.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
