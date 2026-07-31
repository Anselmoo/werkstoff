#!/usr/bin/env python3
"""Tests for confab-cycle's constraint-domain picker.

Reproduces the Phase 2 benchmark finding (docs/plugin-benchmark-phase2-
results.md, CON-1/CON-2): on a fresh ledger, plan-next-pass ignored every
domain's own standalone *_summary.json sidecar and always picked
DOMAIN_ORDER_FALLBACK[0], even when a different domain's sidecar had real,
already-known findings sitting on disk. These tests exercise the actual
CLI as a subprocess against a throwaway repo, the same way
hooks/test_guard_edit_scope.py does.

Run: python3 plugins/confab/scripts/test_cycle_engine.py
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ENGINE = Path(__file__).parent / "cycle_engine.py"


class Repo:
    """A throwaway repo, optionally with domain summary sidecars pre-seeded."""

    def __init__(self, summaries: dict[str, list[dict]] | None = None):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        analysis = self.root / "analysis" / "confab"
        analysis.mkdir(parents=True)
        for domain, findings in (summaries or {}).items():
            summary = {"domain": domain, "findings": findings, "verificationRan": True}
            (analysis / f"{domain}_summary.json").write_text(json.dumps(summary))

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.tmp.cleanup()


def finding(severity: str, category: str = "some-category") -> dict:
    return {
        "severity": severity,
        "title": f"a {severity} finding",
        "evidence": "src/x.py:1",
        "category": category,
        "fixability": "advisory",
    }


def plan_next_pass(repo: Repo, *, mode: str = "propose") -> dict:
    r = subprocess.run(
        [sys.executable, str(ENGINE), "plan-next-pass", str(repo.root), "--mode", mode],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, f"plan-next-pass failed: {r.stderr}"
    return json.loads(r.stdout)


def record_pass_result(repo: Repo, pass_json: dict) -> dict:
    path = repo.root / "pass.json"
    path.write_text(json.dumps(pass_json))
    r = subprocess.run(
        [sys.executable, str(ENGINE), "record-pass-result", str(repo.root), "--pass-json", str(path)],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, f"record-pass-result failed: {r.stderr}"
    return json.loads(r.stdout)


class ConstraintDomainSelectionTests(unittest.TestCase):
    def test_no_sidecars_falls_back_to_canonical_order(self):
        with Repo() as repo:
            plan = plan_next_pass(repo)
        self.assertEqual(plan["domain"], "dependency_audit")

    def test_sidecar_findings_in_a_non_default_domain_are_now_picked(self):
        # The exact CON-1/CON-2 shape: dependency_audit's sidecar has zero
        # findings, assertion_audit's has real ones -- the fix must pick
        # assertion_audit, not silently default to dependency_audit.
        with Repo({
            "dependency_audit": [],
            "assertion_audit": [finding("Medium"), finding("Low")],
        }) as repo:
            plan = plan_next_pass(repo)
        self.assertEqual(plan["domain"], "assertion_audit")

    def test_high_severity_sidecar_findings_outrank_more_numerous_lower_ones(self):
        with Repo({
            "dependency_audit": [finding("Low"), finding("Low"), finding("Low")],
            "contract_drift": [finding("High")],
        }) as repo:
            plan = plan_next_pass(repo)
        self.assertEqual(plan["domain"], "contract_drift")

    def test_empty_sidecar_findings_list_is_ignored(self):
        with Repo({"agentic_reliability": []}) as repo:
            plan = plan_next_pass(repo)
        self.assertEqual(plan["domain"], "dependency_audit")

    def test_malformed_sidecar_does_not_crash_plan_next_pass(self):
        with Repo() as repo:
            (repo.root / "analysis" / "confab" / "contract_drift_summary.json").write_text("not json")
            plan = plan_next_pass(repo)
        self.assertEqual(plan["domain"], "dependency_audit")

    def test_once_ledger_has_findings_sidecars_no_longer_drive_selection(self):
        # Regression guard: this fix must only change behavior for a
        # ledger with zero findings recorded. Once a pass has upserted a
        # real finding into the ledger, the original ledger-based logic
        # (escalated > open_high > open_total) must still govern, even if
        # some other domain's sidecar also has findings sitting on disk.
        with Repo({"assertion_audit": [finding("High")]}) as repo:
            record_pass_result(repo, {
                "passNumber": 1, "domain": "dependency_audit", "mode": "propose",
                "outcomes": [{
                    "findingId": "dep-1", "category": "hallucinated-dependency",
                    "evidence": "requirements.txt:3", "severity": "Low", "outcome": "drafted",
                }],
            })
            plan = plan_next_pass(repo)
        # dependency_audit has one real open ledger finding; assertion_audit
        # has zero ledger findings (only a sidecar, never ingested) -- the
        # ledger-based branch must still pick dependency_audit here.
        self.assertEqual(plan["domain"], "dependency_audit")


if __name__ == "__main__":
    unittest.main()
