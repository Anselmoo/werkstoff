#!/usr/bin/env python3
"""Tests for cupertino's state.py flag store.

Reproduces the Phase 2 benchmark finding (docs/plugin-benchmark-phase2-
results.md, CUP-1/CUP-2/CUP-3): every internal cupertino-review stage
transition re-sent the verbatim original human prompt, with zero trace of
the prior stage's real output -- even though state.py's `set <flag> <value>`
already supported carrying arbitrary content, no skill ever passed anything
but the default placeholder value "1". These tests confirm the mechanism
itself (set/check/clear round-tripping real JSON content, not just a
boolean marker) actually works, since cupertino-review's own instruction to
use it is SKILL.md prose, not code -- this is the one piece of the fix that
can be verified mechanically.

Run: python3 plugins/cupertino/scripts/test_state.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

STATE_PY = Path(__file__).parent / "state.py"


def run(args, cwd, env_extra=None):
    env = {**os.environ, **(env_extra or {})}
    return subprocess.run(
        [sys.executable, str(STATE_PY), *args],
        cwd=cwd, capture_output=True, text=True, env=env,
    )


class StateFlagTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = self.tmp.name
        # state.py resolves its root from CLAUDE_PROJECT_DIR first, cwd as
        # fallback -- pin it explicitly so this test never depends on the
        # test runner's own cwd.
        self.env = {"CLAUDE_PROJECT_DIR": self.repo}
        run(["init"], self.repo, self.env)

    def tearDown(self):
        self.tmp.cleanup()

    def test_default_value_is_still_the_boolean_placeholder(self):
        # Regression guard: existing callers that never pass a value (e.g.
        # any external caller relying on the old "1" default) must be
        # unaffected by this fix.
        r = run(["set", "backwards-done"], self.repo, self.env)
        self.assertEqual(r.returncode, 0)
        r = run(["check", "backwards-done"], self.repo, self.env)
        out = json.loads(r.stdout)
        self.assertEqual(out, {"ok": True, "set": True, "value": "1"})

    def test_real_json_content_round_trips_through_set_and_check(self):
        # The actual fix: a stage's full structured result, not a placeholder.
        payload = json.dumps({
            "literalRequest": "a button that exports to PDF",
            "underlyingProblem": "sharing a snapshot of the current state with someone offline",
            "statement": "a person can hand someone else exactly what they're looking at right now",
            "techDirection": "server-side render to PDF on demand",
            "driftRisks": ["a settings screen for export options that serves configurability, not the stated experience"],
        })
        r = run(["set", "backwards-done", payload], self.repo, self.env)
        self.assertEqual(r.returncode, 0)
        r = run(["check", "backwards-done"], self.repo, self.env)
        out = json.loads(r.stdout)
        self.assertTrue(out["set"])
        # The value must come back byte-identical -- this is exactly the
        # HANDOFF_WORKED test from the Phase 2 benchmark plan: a downstream
        # consumer must be able to recover the upstream stage's real content,
        # not a paraphrase.
        self.assertEqual(json.loads(out["value"]), json.loads(payload))

    def test_stage_output_flags_are_independent_of_each_other(self):
        run(["set", "focus-output", json.dumps({"survivors": [{"name": "A", "description": "..."}]})],
            self.repo, self.env)
        run(["set", "longevity-output", json.dumps({"dimensionScores": [3, 4, 2, 5, 3, 4]})],
            self.repo, self.env)
        focus = json.loads(run(["check", "focus-output"], self.repo, self.env).stdout)
        longevity = json.loads(run(["check", "longevity-output"], self.repo, self.env).stdout)
        self.assertIn("survivors", focus["value"])
        self.assertIn("dimensionScores", longevity["value"])

    def test_unset_stage_output_is_reported_as_not_set_not_fabricated(self):
        r = run(["check", "integrate-output"], self.repo, self.env)
        out = json.loads(r.stdout)
        self.assertEqual(out, {"ok": True, "set": False})

    def test_clear_removes_a_content_bearing_flag_same_as_a_placeholder_one(self):
        run(["set", "council-output", json.dumps({"lenses": ["Reduction"]})], self.repo, self.env)
        self.assertTrue(json.loads(run(["check", "council-output"], self.repo, self.env).stdout)["set"])
        run(["clear", "council-output"], self.repo, self.env)
        self.assertFalse(json.loads(run(["check", "council-output"], self.repo, self.env).stdout)["set"])

    def test_a_fresh_review_run_starts_clean_after_clearing_every_flag(self):
        # Simulates cupertino-review's own "Before you start" sweep: every
        # flag from a hypothetical prior run is cleared, and a fresh run
        # cannot see stale content from an earlier, unrelated scope.
        stage_flags = [
            "backwards-done", "focus-output", "longevity-output", "integrate-output",
            "council-output", "prototype-output", "elevate-output", "unbox-output",
        ]
        for flag in stage_flags:
            run(["set", flag, json.dumps({"stale": "from a previous review"})], self.repo, self.env)
        for flag in stage_flags:
            run(["clear", flag], self.repo, self.env)
        for flag in stage_flags:
            out = json.loads(run(["check", flag], self.repo, self.env).stdout)
            self.assertFalse(out["set"], f"{flag} should be cleared, got {out}")


if __name__ == "__main__":
    unittest.main()
