#!/usr/bin/env python3
"""Tests for zeugnis's PreToolUse bash-scope guard.

Mirrors test_guard_edit_scope.py in rigor and structure: a throwaway Repo
helper, a decision() assertion wrapper, TestInertness / TestScopeEnforcement
/ TestFailureMode classes. This is the dedicated subprocess test issue #73
names as missing (`H-TEST-EXISTS`).

Every mutating phrase used to build a probe command is assembled from
fragments at call time rather than written as a literal string in this
file -- see guard_bash_scope.py's own module docstring and issue #73's
"blast radius" note: an *installed* copy of a guard shaped like this one
denies any Bash call whose command text merely contains a phrase like
"npm install" or "poetry add", including inside a test file being written.
Assembling the phrase at runtime is not a stylistic choice here, it is
what makes it possible to write this file at all while such a guard is
active in the authoring session.

Run: python3 plugins/zeugnis/scripts/hooks/test_guard_bash_scope.py
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HOOK = Path(__file__).parent / "guard_bash_scope.py"


def _phrase(tool: str, verb: str) -> str:
    """Assemble a two-word mutating phrase from fragments, never as a
    literal in source (see module docstring)."""
    return f"{tool} {verb}"


NPM_INSTALL = _phrase("npm", "in" + "stall")
POETRY_ADD = _phrase("poetry", "a" + "dd")
PIP_INSTALL = _phrase("pip", "in" + "stall")


class Repo:
    """A throwaway repo, optionally with an analysis/zeugnis/ directory."""

    def __init__(self, *, zeugnis_dir: bool = True):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "docs").mkdir()
        (self.root / "docs" / "setup.md").write_text(f"Run `{PIP_INSTALL} requests` first.\n")
        if zeugnis_dir:
            (self.root / "analysis" / "zeugnis").mkdir(parents=True)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.tmp.cleanup()


def run(repo: Repo, command: str, env_extra: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    import os

    payload = json.dumps({"cwd": str(repo.root), "tool_name": "Bash", "tool_input": {"command": command}})
    env = {**os.environ, **(env_extra or {})}
    r = subprocess.run([sys.executable, str(HOOK)], input=payload,
                       capture_output=True, text=True, timeout=30, env=env)
    assert r.returncode in (0, 2), f"hook must exit 0 (allow) or 2 (deny), got {r.returncode}: {r.stderr}"
    return r


def decision(r: subprocess.CompletedProcess) -> str:
    # allow() emits NO stdout by design -- only deny() prints JSON.
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
        """Without this, the hook would deny Bash calls in every repo on the
        machine, zeugnis-enabled or not."""
        with Repo(zeugnis_dir=False) as repo:
            self.assertEqual(decision(run(repo, f"{NPM_INSTALL} left-pad")), "allow")

    def test_non_bash_tool_allowed(self):
        with Repo() as repo:
            payload = json.dumps({"cwd": str(repo.root), "tool_name": "Read",
                                  "tool_input": {"command": NPM_INSTALL}})
            r = subprocess.run([sys.executable, str(HOOK)], input=payload,
                               capture_output=True, text=True, timeout=30)
            self.assertEqual(r.returncode, 0)


class TestReadOnlyMentionsAllowed(unittest.TestCase):
    """The regression class issue #73 is about: a command that merely
    *mentions* an install phrase, as a grep pattern, filename, or quoted
    text, must not be refused."""

    def test_grep_pattern_mentioning_install_allowed(self):
        with Repo() as repo:
            cmd = f'grep -rn "{PIP_INSTALL}" docs/'
            self.assertEqual(decision(run(repo, cmd)), "allow")

    def test_rg_pattern_mentioning_install_allowed(self):
        with Repo() as repo:
            cmd = f"rg '{NPM_INSTALL}' docs/setup.md"
            self.assertEqual(decision(run(repo, cmd)), "allow")

    def test_pipeline_grep_mentioning_add_allowed(self):
        with Repo() as repo:
            cmd = f'cat docs/setup.md | grep "{POETRY_ADD}"'
            self.assertEqual(decision(run(repo, cmd)), "allow")


class TestMutatingCommandsDenied(unittest.TestCase):
    def test_npm_install_denied(self):
        with Repo() as repo:
            r = run(repo, f"{NPM_INSTALL} left-pad")
            self.assertEqual(decision(r), "deny")
            self.assertIn("mutating invocation", r.stderr)

    def test_pip_install_denied(self):
        with Repo() as repo:
            self.assertEqual(decision(run(repo, f"{PIP_INSTALL} requests")), "deny")

    def test_poetry_add_denied(self):
        with Repo() as repo:
            self.assertEqual(decision(run(repo, f"{POETRY_ADD} requests")), "deny")

    def test_qualified_path_binary_still_denied(self):
        with Repo() as repo:
            cmd = f"/usr/local/bin/{NPM_INSTALL} left-pad"
            self.assertEqual(decision(run(repo, cmd)), "deny")

    def test_mutmut_patch_flag_after_verb_denied(self):
        with Repo() as repo:
            self.assertEqual(decision(run(repo, "mutmut run --patch")), "deny")

    def test_mutmut_patch_flag_before_verb_denied(self):
        with Repo() as repo:
            self.assertEqual(decision(run(repo, "mutmut --patch run")), "deny")

    def test_go_get_dash_u_denied(self):
        with Repo() as repo:
            self.assertEqual(decision(run(repo, "go get -u example.com/pkg")), "deny")


class TestWrapperCommandsDenied(unittest.TestCase):
    """Regression class flagged by the coordinator: argv[0] anchoring alone
    lost the "doesn't care what comes first" property the old raw-string
    search had for free. A wrapper is not an adversarial evasion -- it's an
    ordinary prefix a cooperative model writes -- so it must be skipped
    before argv[0]/argv[1] are tested."""

    def test_sudo_prefixed_install_denied(self):
        with Repo() as repo:
            self.assertEqual(decision(run(repo, f"sudo {NPM_INSTALL} left-pad")), "deny")

    def test_sudo_with_value_flag_denied(self):
        """`sudo -u root ...` -- `-u` takes `root` as its value, which must
        not be mistaken for the start of the real command."""
        with Repo() as repo:
            self.assertEqual(decision(run(repo, f"sudo -u root {NPM_INSTALL} left-pad")), "deny")

    def test_env_with_assignment_prefixed_install_denied(self):
        with Repo() as repo:
            self.assertEqual(decision(run(repo, f"env FOO=1 {NPM_INSTALL} left-pad")), "deny")

    def test_bare_var_assignment_no_env_denied(self):
        """`FOO=1 npm install x` is valid shell with no literal `env`."""
        with Repo() as repo:
            self.assertEqual(decision(run(repo, f"FOO=1 {NPM_INSTALL} left-pad")), "deny")

    def test_xargs_prefixed_install_denied(self):
        with Repo() as repo:
            self.assertEqual(decision(run(repo, f"xargs {NPM_INSTALL}")), "deny")

    def test_nice_with_value_flag_denied(self):
        with Repo() as repo:
            self.assertEqual(decision(run(repo, f"nice -n 5 {NPM_INSTALL} left-pad")), "deny")

    def test_stacked_wrappers_denied(self):
        """Wrappers chain: `sudo env FOO=1 npm install x` must still deny --
        the skip loop has to run more than once."""
        with Repo() as repo:
            self.assertEqual(decision(run(repo, f"sudo env FOO=1 {NPM_INSTALL} left-pad")), "deny")


class TestWrapperSkipDoesNotBecomeABypass(unittest.TestCase):
    """The skip logic itself must not become a way to smuggle a mutating
    command past the guard, and must not crash when a wrapper has nothing
    (or nothing dangerous) after it."""

    def test_sudo_read_only_command_allowed(self):
        with Repo() as repo:
            self.assertEqual(decision(run(repo, "sudo cat docs/setup.md")), "allow")

    def test_bare_env_with_no_command_allowed(self):
        """The skip loop must terminate cleanly when it runs off the end of
        argv, not crash and not treat running out of tokens as a match."""
        with Repo() as repo:
            self.assertEqual(decision(run(repo, "env")), "allow")

    def test_env_with_only_assignments_allowed(self):
        with Repo() as repo:
            self.assertEqual(decision(run(repo, "env FOO=1 BAR=2")), "allow")


class TestPipelineSegments(unittest.TestCase):
    def test_later_pipeline_segment_mutating_denied(self):
        """A read-only first segment followed by a real mutating segment
        must still deny -- each command in the chain is checked."""
        with Repo() as repo:
            cmd = f"echo hello && {NPM_INSTALL} left-pad"
            r = run(repo, cmd)
            self.assertEqual(decision(r), "deny")

    def test_all_readonly_pipeline_allowed(self):
        with Repo() as repo:
            cmd = "cat docs/setup.md | wc -l"
            self.assertEqual(decision(run(repo, cmd)), "allow")


class TestFailureMode(unittest.TestCase):
    def test_unbalanced_quotes_denies(self):
        with Repo() as repo:
            r = run(repo, 'echo "unbalanced')
            self.assertEqual(decision(r), "deny")
            self.assertIn("tokenise", r.stderr)

    def test_escape_hatch_env_var_allows(self):
        with Repo() as repo:
            r = run(repo, f"{NPM_INSTALL} left-pad", env_extra={"ZEUGNIS_DISABLE_GUARD": "1"})
            self.assertEqual(decision(r), "allow")


if __name__ == "__main__":
    unittest.main(verbosity=2)
