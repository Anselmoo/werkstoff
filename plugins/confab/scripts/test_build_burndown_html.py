#!/usr/bin/env python3
"""Tests for confab-status's burndown chart builder.

Exercises the actual CLI as a subprocess against a throwaway repo with a
hand-seeded ledger.json, the same way test_cycle_engine.py does. Covers the
--d3/--tokens injection contract this task adds to build_burndown_html.py,
and (as regression coverage for the template rewrite done in Tasks 1-3 of
this plan) the split-view structure and canonical token names the rebuilt
burndown-viewer.html must contain.

Run: python3 plugins/confab/scripts/test_build_burndown_html.py -v
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
BUILDER = SCRIPT_DIR / "build_burndown_html.py"
TEMPLATE = SCRIPT_DIR.parent / "assets" / "burndown-viewer.html"
D3 = SCRIPT_DIR.parent / "assets" / "inline-d3.html"
TOKENS = SCRIPT_DIR.parent / "assets" / "tokens.css"


class Repo:
    """A throwaway repo with a hand-seeded analysis/confab/ledger.json."""

    def __init__(self, ledger: dict):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        analysis = self.root / "analysis" / "confab"
        analysis.mkdir(parents=True)
        (analysis / "ledger.json").write_text(json.dumps(ledger))

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.tmp.cleanup()


THREE_PASS_LEDGER = {
    "totalPasses": 3,
    "passes": [
        {"passNumber": 1, "domain": "dependency_audit", "closed": 2, "fixOrDraftOutcomes": 3},
        {"passNumber": 2, "domain": "assertion_audit", "closed": 1, "fixOrDraftOutcomes": 1},
        {"passNumber": 3, "domain": "contract_drift", "closed": 0, "fixOrDraftOutcomes": 0},
    ],
    "findings": {
        "F1": {"status": "closed", "domain": "dependency_audit", "category": "c", "severity": "High", "reopenCount": 0},
        "F2": {"status": "open", "domain": "assertion_audit", "category": "c", "severity": "Low", "reopenCount": 0},
        "F3": {"status": "escalated", "domain": "contract_drift", "category": "c", "severity": "Medium", "reopenCount": 4},
    },
}


def run_builder(repo: Repo, extra_args: list[str]) -> subprocess.CompletedProcess:
    out_path = repo.root / "BURNDOWN.html"
    args = [
        sys.executable, str(BUILDER), str(repo.root),
        "--template", str(TEMPLATE),
        "--out", str(out_path),
        *extra_args,
    ]
    return subprocess.run(args, capture_output=True, text=True)


def run_builder_with_both_flags(repo: Repo) -> subprocess.CompletedProcess:
    return run_builder(repo, ["--d3", str(D3), "--tokens", str(TOKENS)])


class CliFlagTests(unittest.TestCase):
    def test_missing_d3_flag_fails_argparse(self):
        with Repo(THREE_PASS_LEDGER) as repo:
            r = run_builder(repo, ["--tokens", str(TOKENS)])
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("--d3", r.stderr)

    def test_missing_tokens_flag_fails_argparse(self):
        with Repo(THREE_PASS_LEDGER) as repo:
            r = run_builder(repo, ["--d3", str(D3)])
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("--tokens", r.stderr)

    def test_both_flags_present_succeeds_and_reports_totals(self):
        with Repo(THREE_PASS_LEDGER) as repo:
            r = run_builder_with_both_flags(repo)
        self.assertEqual(r.returncode, 0, r.stderr)
        payload = json.loads(r.stdout)
        self.assertEqual(payload["totalPasses"], 3)


class InjectionContentTests(unittest.TestCase):
    def test_d3_bundle_is_inlined(self):
        with Repo(THREE_PASS_LEDGER) as repo:
            r = run_builder_with_both_flags(repo)
            self.assertEqual(r.returncode, 0, r.stderr)
            html = Path(json.loads(r.stdout)["burndownPath"]).read_text(encoding="utf-8")
        self.assertIn("window.d3", html)
        self.assertNotIn("<!--__D3_SUBSET__-->", html)

    def test_canonical_tokens_are_inlined_and_legacy_names_are_gone(self):
        with Repo(THREE_PASS_LEDGER) as repo:
            r = run_builder_with_both_flags(repo)
            self.assertEqual(r.returncode, 0, r.stderr)
            html = Path(json.loads(r.stdout)["burndownPath"]).read_text(encoding="utf-8")
        for canonical in ("--status-good:", "--status-bad:", "--status-warn:", "--accent-2:", "--panel:", "--muted:"):
            self.assertIn(canonical, html)
        for legacy in ("--bg-panel:", "--text-dim:", "--bg-header:", "--cumulative:", "--closed:", "--outcomes:", "--open:", "--escalated:"):
            self.assertNotIn(legacy, html)
        self.assertNotIn("/*__TOKENS__*/", html)

    def test_data_payload_is_embedded(self):
        with Repo(THREE_PASS_LEDGER) as repo:
            r = run_builder_with_both_flags(repo)
            self.assertEqual(r.returncode, 0, r.stderr)
            html = Path(json.loads(r.stdout)["burndownPath"]).read_text(encoding="utf-8")
        self.assertIn('"totalPasses": 3', html)


class SplitViewStructureTests(unittest.TestCase):
    def test_two_named_views_and_no_combined_chart_function(self):
        with Repo(THREE_PASS_LEDGER) as repo:
            r = run_builder_with_both_flags(repo)
            self.assertEqual(r.returncode, 0, r.stderr)
            html = Path(json.loads(r.stdout)["burndownPath"]).read_text(encoding="utf-8")
        self.assertIn('id="view-trend"', html)
        self.assertIn('id="view-breakdown"', html)
        self.assertIn("renderTrendChart", html)
        self.assertNotIn("function renderChart(", html)


if __name__ == "__main__":
    unittest.main()
