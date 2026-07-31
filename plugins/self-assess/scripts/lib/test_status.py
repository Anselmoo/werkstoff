#!/usr/bin/env python3
"""Tests for self-assess-status's dashboard builder.

Reproduces the Phase 2 benchmark finding (docs/plugin-benchmark-phase2-
results.md, SA-2): self-assess-stage-map's real, schema-validated
stage_graph.json sidecar was invisible to `self-assess-status` -- its
`present` map only ever tracked the 7 findings-domain sidecars, so a user
asking "where does self-assess stand" got no signal that stage-map had
already run. These tests confirm the fix (a separate `structural` map,
never merged into `present`/recommend_transform_brief) actually works.

Run: python3 plugins/self-assess/scripts/lib/test_status.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib import status  # noqa: E402


def _write(output_abs: str, filename: str, content: dict | None = None) -> None:
    os.makedirs(output_abs, exist_ok=True)
    with open(os.path.join(output_abs, filename), "w", encoding="utf-8") as fh:
        json.dump(content or {}, fh)


class StatusDashboardTests(unittest.TestCase):
    def test_empty_output_dir_has_nothing_present_or_structural(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(status.build_present_artifacts(d), {})
            self.assertEqual(status.build_structural_artifacts(d), {})

    def test_stage_map_sidecar_is_now_visible_via_structural(self):
        # The exact SA-2 shape: only stage-map has run, nothing else.
        with tempfile.TemporaryDirectory() as d:
            _write(d, "stage_map_summary.json")
            self.assertEqual(status.build_present_artifacts(d), {})
            self.assertEqual(
                status.build_structural_artifacts(d),
                {"self-assess-stage-map": "stage_map_summary.json"},
            )

    def test_all_three_structural_skills_tracked_independently(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "stage_map_summary.json")
            _write(d, "complexity_score_summary.json")
            structural = status.build_structural_artifacts(d)
            self.assertEqual(
                structural,
                {
                    "self-assess-stage-map": "stage_map_summary.json",
                    "self-assess-complexity-score": "complexity_score_summary.json",
                },
            )
            self.assertNotIn("self-assess-transform-brief", structural)

    def test_structural_artifacts_never_leak_into_present(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "stage_map_summary.json")
            _write(d, "complexity_score_summary.json")
            _write(d, "transform_brief_summary.json")
            self.assertEqual(status.build_present_artifacts(d), {})

    def test_structural_artifacts_never_trigger_transform_brief_recommendation(self):
        # recommend_transform_brief's "has_any_finding_artifact" check must
        # stay scoped to SIDECAR_FILES only -- a structural-only repo (stage
        # map run, no actual findings domain run yet) must not recommend a
        # brief just because *something* is on disk.
        with tempfile.TemporaryDirectory() as d:
            _write(d, "stage_map_summary.json")
            self.assertFalse(status.recommend_transform_brief(d))

    def test_findings_artifact_still_triggers_transform_brief_recommendation(self):
        # Regression guard: a real findings-domain sidecar with no brief yet
        # must still recommend one -- unaffected by this fix.
        with tempfile.TemporaryDirectory() as d:
            _write(d, "lint_audit_summary.json")
            self.assertTrue(status.recommend_transform_brief(d))

    def test_findings_and_structural_coexist_without_interference(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "lint_audit_summary.json")
            _write(d, "stage_map_summary.json")
            self.assertEqual(
                status.build_present_artifacts(d), {"self-assess-lint-audit": "lint_audit_summary.json"})
            self.assertEqual(
                status.build_structural_artifacts(d),
                {"self-assess-stage-map": "stage_map_summary.json"})
            self.assertTrue(status.recommend_transform_brief(d))


if __name__ == "__main__":
    unittest.main()
