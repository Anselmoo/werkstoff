#!/usr/bin/env python3
"""Tests for self-assess-autopilot's stage-map freshness check.

Reproduces the Phase 2 benchmark finding (docs/plugin-benchmark-phase2-
results.md, SA-1): self-assess-autopilot always re-ran self-assess-stage-map
from scratch, even seconds after a fresh, valid, unstale stage_graph.json had
already been written in the same session -- there was no staleness/existence
check on stage_graph.json/file_stage_index.json anywhere in its SKILL.md.
These tests exercise the real logic (`staleness.stage_map_fresh`) against a
real git repo -- commit timestamps and file mtimes are both genuine, not
mocked, since that's exactly the comparison this check has to get right.

Run: python3 plugins/self-assess/scripts/lib/test_staleness.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib import staleness  # noqa: E402


def _git(args, cwd):
    subprocess.run(["git", *args], cwd=cwd, capture_output=True, check=True)


class StageMapFreshRepo:
    """A throwaway git repo with a controllable commit history and an
    analysis/self-assess output dir, so tests can construct real
    before/after-the-latest-commit scenarios instead of mocking mtimes."""

    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        _git(["init", "-q"], self.root)
        _git(["config", "user.email", "t@t.com"], self.root)
        _git(["config", "user.name", "t"], self.root)
        self.output_abs = os.path.join(self.root, "analysis", "self-assess")
        os.makedirs(self.output_abs, exist_ok=True)

    def commit(self, message="commit"):
        readme = os.path.join(self.root, "README.md")
        with open(readme, "a", encoding="utf-8") as fh:
            fh.write(f"{message}\n")
        _git(["add", "-A"], self.root)
        _git(["commit", "-q", "-m", message], self.root)
        time.sleep(1.05)  # git commit timestamps and mtimes are second-granularity

    def write_artifact(self, name):
        with open(os.path.join(self.output_abs, name), "w", encoding="utf-8") as fh:
            fh.write("{}")

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.tmp.cleanup()


class StageMapFreshTests(unittest.TestCase):
    def test_no_artifacts_at_all_is_not_fresh(self):
        with StageMapFreshRepo() as repo:
            repo.commit()
            self.assertFalse(staleness.stage_map_fresh(repo.output_abs, repo.root))

    def test_only_one_of_the_two_required_artifacts_is_not_fresh(self):
        with StageMapFreshRepo() as repo:
            repo.commit()
            repo.write_artifact("stage_graph.json")
            # file_stage_index.json missing -- a prior run was interrupted before finishing.
            self.assertFalse(staleness.stage_map_fresh(repo.output_abs, repo.root))

    def test_both_artifacts_written_after_latest_commit_is_fresh(self):
        with StageMapFreshRepo() as repo:
            repo.commit()
            repo.write_artifact("stage_graph.json")
            repo.write_artifact("file_stage_index.json")
            self.assertTrue(staleness.stage_map_fresh(repo.output_abs, repo.root))

    def test_repo_changed_since_artifacts_were_written_is_not_fresh(self):
        # The exact SA-1 shape inverted: this time the repo really DID change
        # since stage-map ran, so re-running is the correct answer.
        with StageMapFreshRepo() as repo:
            repo.commit()
            repo.write_artifact("stage_graph.json")
            repo.write_artifact("file_stage_index.json")
            time.sleep(1.1)  # force the next commit into a strictly later second
            repo.commit("a later commit that invalidates the stage map")
            self.assertFalse(staleness.stage_map_fresh(repo.output_abs, repo.root))

    def test_one_artifact_stale_and_the_other_fresh_is_not_fresh_overall(self):
        with StageMapFreshRepo() as repo:
            repo.commit()
            repo.write_artifact("stage_graph.json")
            time.sleep(1.1)  # force this commit into a strictly later second than the write above
            repo.commit("invalidates only the first artifact's freshness")
            time.sleep(1.1)  # force this write into a strictly later second than the commit above
            repo.write_artifact("file_stage_index.json")
            self.assertFalse(staleness.stage_map_fresh(repo.output_abs, repo.root))

    def test_no_commits_at_all_is_not_fresh(self):
        # Staleness is undeterminable with zero commits -- "unknown" must
        # never be treated as "fresh."
        with StageMapFreshRepo() as repo:
            repo.write_artifact("stage_graph.json")
            repo.write_artifact("file_stage_index.json")
            self.assertFalse(staleness.stage_map_fresh(repo.output_abs, repo.root))

    def test_not_a_git_repo_is_not_fresh(self):
        with tempfile.TemporaryDirectory() as d:
            output_abs = os.path.join(d, "analysis", "self-assess")
            os.makedirs(output_abs, exist_ok=True)
            for name in staleness.STAGE_MAP_REQUIRED_ARTIFACTS:
                with open(os.path.join(output_abs, name), "w", encoding="utf-8") as fh:
                    fh.write("{}")
            self.assertFalse(staleness.stage_map_fresh(output_abs, d))


if __name__ == "__main__":
    unittest.main()
