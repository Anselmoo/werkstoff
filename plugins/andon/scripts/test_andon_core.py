#!/usr/bin/env python3
"""Tests for andon_core.route_wire -- the wire classifier andon-verify executes --
and for validate_doc's check that evidence stays within route_wire's tier_ceiling.

The defect these pin down: degradation walked prerequisites only, so any wire
whose strategy lacked its prerequisite landed on 'b' (numerical V&V) -- a
strategy whose reference demands a numeric quantity the wire never had.
Run: python3 test_andon_core.py
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).parent
sys.path.insert(0, str(SCRIPTS))

import andon_core  # noqa: E402

ALL_FALSE_SIGNALS = {
    "is_structural_claim": False,
    "is_numerical": False,
    "is_property_invariant": False,
    "is_verifier_of_verifier": False,
    "is_autonomous_reliability": False,
    "is_epistemic_claim": False,
}
NOTHING_AVAILABLE = {
    "available_lsp_or_index": False,
    "available_property_lib": False,
    "available_zeugnis": False,
}


def signals(**on):
    return {**ALL_FALSE_SIGNALS, **on}


def available(**on):
    return {**NOTHING_AVAILABLE, **on}


class RouteWire(unittest.TestCase):
    def test_structural_without_index_stays_e_at_tier_2(self):
        r = andon_core.route_wire(signals(is_structural_claim=True), available(available_zeugnis=True))
        self.assertEqual(r["strategy"], "e", "a structural claim must never be routed to numerical V&V")
        self.assertIsNone(r["degraded_from"], "e does not degrade to another strategy; it caps its tier")
        self.assertEqual(r["tier_ceiling"], 2)

    def test_structural_with_index_allows_tier_1(self):
        r = andon_core.route_wire(signals(is_structural_claim=True), available(available_lsp_or_index=True))
        self.assertEqual(r["strategy"], "e")
        self.assertEqual(r["tier_ceiling"], 1)

    def test_numerical_routes_to_b_with_nothing_available(self):
        r = andon_core.route_wire(signals(is_numerical=True), available())
        self.assertEqual(r["strategy"], "b")
        self.assertIsNone(r["degraded_from"])
        self.assertIsNone(r["tier_ceiling"], "tier_ceiling is only meaningful for e")

    def test_property_without_property_lib_degrades_to_a_not_b(self):
        r = andon_core.route_wire(signals(is_property_invariant=True), available())
        self.assertEqual(r["strategy"], "a")
        self.assertEqual(r["degraded_from"], "f")

    def test_property_without_lib_but_verifier_trigger_lands_on_g(self):
        # The walk still prefers a LATER strategy whose own trigger fired.
        r = andon_core.route_wire(signals(is_property_invariant=True, is_verifier_of_verifier=True), available())
        self.assertEqual(r["strategy"], "g")
        self.assertEqual(r["degraded_from"], "f")

    def test_property_with_lib_routes_to_f(self):
        r = andon_core.route_wire(signals(is_property_invariant=True), available(available_property_lib=True))
        self.assertEqual(r["strategy"], "f")
        self.assertIsNone(r["degraded_from"])

    def test_agentic_reliability_without_zeugnis_degrades_to_a_not_b(self):
        r = andon_core.route_wire(signals(is_autonomous_reliability=True), available())
        self.assertEqual(r["strategy"], "a")
        self.assertEqual(r["degraded_from"], "d")

    def test_all_false_reaches_a(self):
        r = andon_core.route_wire(signals(), available())
        self.assertEqual(r["strategy"], "a")
        self.assertIsNone(r["degraded_from"])
        self.assertEqual(r["checked_order"], andon_core.CLASSIFIER_ORDER)

    def test_no_degradation_ever_lands_on_an_untriggered_strategy(self):
        # Exhaustive over all 2^6 signal x 2^3 availability combinations.
        sig_keys = list(ALL_FALSE_SIGNALS)
        av_keys = list(NOTHING_AVAILABLE)
        for s_bits in range(2 ** len(sig_keys)):
            sig = {k: bool(s_bits >> i & 1) for i, k in enumerate(sig_keys)}
            for a_bits in range(2 ** len(av_keys)):
                av = {k: bool(a_bits >> i & 1) for i, k in enumerate(av_keys)}
                r = andon_core.route_wire(sig, av)
                flag = andon_core.TRIGGER_FLAG_BY_STRATEGY[r["strategy"]]
                with self.subTest(signals=sig, availability=av, routed=r):
                    self.assertTrue(flag is None or sig[flag])
                    prereq = andon_core.PREREQ_FLAG_BY_STRATEGY[r["strategy"]]
                    self.assertTrue(prereq is None or av[prereq])

    def test_cli_reproduction_from_bug_report(self):
        out = subprocess.run(
            [sys.executable, str(SCRIPTS / "andon_core.py"), "route-wire",
             json.dumps(signals(is_structural_claim=True)),
             json.dumps(available(available_zeugnis=True))],
            capture_output=True, text=True, check=True,
        )
        r = json.loads(out.stdout)
        self.assertEqual((r["strategy"], r["degraded_from"], r["tier_ceiling"]), ("e", None, 2))


def structural_evidence(**overrides):
    return {
        "type": "evidence",
        "title": "import edge claim",
        "wire": "a->b",
        "strategy": "e",
        "verdict": "red",
        "tier": 2,
        "tier_ceiling": 2,
        "non_overridable": False,
        **overrides,
    }


class ValidateDocTierCeiling(unittest.TestCase):
    def assertRefused(self, fields, code):
        with self.assertRaises(andon_core.AndonError) as ctx:
            andon_core.validate_doc(fields)
        self.assertEqual(ctx.exception.code, code)

    def test_tier_1_under_ceiling_2_is_refused(self):
        # The exact escalation the ceiling exists to stop: an index-less run
        # labelling a grep result as the non-overridable Tier 1 halt.
        self.assertRefused(structural_evidence(tier=1, non_overridable=True), "SCHEMA_TIER_ABOVE_CEILING")

    def test_missing_ceiling_is_refused_not_defaulted(self):
        fields = structural_evidence()
        del fields["tier_ceiling"]
        self.assertRefused(fields, "SCHEMA_MISSING_TIER_CEILING")

    def test_ceiling_3_is_not_a_route_wire_value(self):
        self.assertRefused(structural_evidence(tier=3, tier_ceiling=3), "SCHEMA_MISSING_TIER_CEILING")

    def test_ceiling_on_non_structural_evidence_is_refused(self):
        self.assertRefused(
            structural_evidence(strategy="a", tier=None, tier_ceiling=2),
            "SCHEMA_TIER_CEILING_ONLY_FOR_E",
        )

    def test_tiers_at_or_below_ceiling_are_accepted(self):
        for tier, ceiling in [(2, 2), (3, 2), (1, 1), (2, 1), (3, 1)]:
            with self.subTest(tier=tier, tier_ceiling=ceiling):
                fields = structural_evidence(tier=tier, tier_ceiling=ceiling, non_overridable=tier == 1)
                self.assertTrue(andon_core.validate_doc(fields))

    def test_non_structural_evidence_without_ceiling_is_accepted(self):
        self.assertTrue(andon_core.validate_doc(structural_evidence(strategy="b", tier=None, tier_ceiling=None)))

    def test_routed_ceiling_round_trips_into_validate_doc(self):
        # route_wire's own output is what the doc must carry -- feed it straight in.
        routed = andon_core.route_wire({"is_structural_claim": True}, {})
        self.assertRefused(
            structural_evidence(tier=1, tier_ceiling=routed["tier_ceiling"], non_overridable=True),
            "SCHEMA_TIER_ABOVE_CEILING",
        )

    def test_write_doc_refuses_before_touching_disk(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(andon_core.AndonError):
                andon_core.write_doc(
                    root, "ledger", "evidence/ev1.md",
                    structural_evidence(tier=1, non_overridable=True),
                )
            self.assertFalse((Path(root) / "ledger").exists())


def simple_evidence(**overrides):
    return {
        "type": "evidence", "title": "wire proven", "wire": "a->b",
        "strategy": "a", "verdict": "green",
        **overrides,
    }


class ValidateDocLifecycleFields(unittest.TestCase):
    """#72: superseded_by, measured_against, valid_until -- evidence-only,
    optional, rejected with SCHEMA_* codes when malformed."""

    def assertRefused(self, fields, code):
        with self.assertRaises(andon_core.AndonError) as ctx:
            andon_core.validate_doc(fields)
        self.assertEqual(ctx.exception.code, code)

    def test_absent_fields_behave_exactly_as_today(self):
        self.assertTrue(andon_core.validate_doc(simple_evidence()))

    def test_all_three_accepted_on_evidence(self):
        self.assertTrue(andon_core.validate_doc(simple_evidence(
            superseded_by="other-slug", measured_against="decision-1",
            valid_until="2099-01-01",
        )))

    def test_superseded_by_on_gap_is_refused(self):
        gap = {
            "type": "gap", "title": "gap with a supersede field",
            "stage": "ingest", "kind": "bug", "status": "open",
            "superseded_by": "something",
        }
        self.assertRefused(gap, "SCHEMA_LIFECYCLE_FIELD_NOT_EVIDENCE")

    def test_measured_against_on_stage_is_refused(self):
        stage = {
            "type": "stage", "title": "ingest", "order": 1,
            "confidence": "heuristic", "measured_against": "decision-1",
        }
        self.assertRefused(stage, "SCHEMA_LIFECYCLE_FIELD_NOT_EVIDENCE")

    def test_empty_superseded_by_is_refused(self):
        self.assertRefused(simple_evidence(superseded_by=""), "SCHEMA_BAD_SUPERSEDED_BY")

    def test_non_string_superseded_by_is_refused(self):
        self.assertRefused(simple_evidence(superseded_by=3), "SCHEMA_BAD_SUPERSEDED_BY")

    def test_empty_measured_against_is_refused(self):
        self.assertRefused(simple_evidence(measured_against=""), "SCHEMA_BAD_MEASURED_AGAINST")

    def test_non_iso_valid_until_is_refused(self):
        self.assertRefused(simple_evidence(valid_until="not-a-date"), "SCHEMA_BAD_VALID_UNTIL")

    def test_impossible_calendar_date_is_refused(self):
        self.assertRefused(simple_evidence(valid_until="2024-02-30"), "SCHEMA_BAD_VALID_UNTIL")

    def test_write_doc_refuses_self_reference(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(andon_core.AndonError) as ctx:
                andon_core.write_doc(
                    root, "ledger", "evidence/ev1.md",
                    simple_evidence(superseded_by="ev1"),
                )
            self.assertEqual(ctx.exception.code, "SCHEMA_SUPERSEDED_BY_SELF")
            self.assertFalse((Path(root) / "ledger").exists())

    def test_write_doc_accepts_reference_to_a_different_slug(self):
        with tempfile.TemporaryDirectory() as root:
            path = andon_core.write_doc(
                root, "ledger", "evidence/ev2.md",
                simple_evidence(superseded_by="ev1"),
            )
            self.assertTrue(Path(path).is_file())


def evidence_doc(slug, **fields):
    return {"path": f"evidence/{slug}.md", "slug": slug, "fields": fields, "body": ""}


class ComputeWireStatusChainHeadResolution(unittest.TestCase):
    """#72: compute_wire_status resolves superseded_by to the chain head
    before judging verdict/expiry -- mirrors hooks/andon_enforce.py's
    stop_reason() evidence loop (probe_lifecycle.py's L1-L4 exercise the
    hook side of the same behaviour end to end)."""

    def test_no_chain_behaves_as_before(self):
        docs = [evidence_doc("e0", wire="a->b", verdict="red"),
                evidence_doc("e1", wire="a->b", verdict="green")]
        self.assertEqual(andon_core.compute_wire_status(docs), "green")

    def test_superseded_leaf_defers_to_head(self):
        docs = [evidence_doc("a-green", wire="a->b", verdict="green"),
                evidence_doc("b-red", wire="a->b", verdict="red", superseded_by="a-green")]
        self.assertEqual(andon_core.compute_wire_status(docs), "green")

    def test_dangling_superseded_by_is_unknown(self):
        docs = [evidence_doc("c-red", wire="a->b", verdict="green", superseded_by="nonexistent")]
        self.assertEqual(andon_core.compute_wire_status(docs), "unknown")

    def test_cycle_is_unknown(self):
        docs = [evidence_doc("x", wire="a->b", verdict="green", superseded_by="y"),
                evidence_doc("y", wire="a->b", verdict="green", superseded_by="x")]
        self.assertEqual(andon_core.compute_wire_status(docs), "unknown")

    def test_multi_hop_chain_resolves_to_true_head(self):
        """v1 (green, the true head) <- v2 (red, superseded_by v1) <- v3 (red,
        superseded_by v2, the filename-latest record). Stopping after one
        hop would read v2's own red verdict and get this wrong; only walking
        the whole chain to v1 gets 'green'."""
        docs = [evidence_doc("v1", wire="a->b", verdict="green"),
                evidence_doc("v2", wire="a->b", verdict="red", superseded_by="v1"),
                evidence_doc("v3", wire="a->b", verdict="red", superseded_by="v2")]
        self.assertEqual(andon_core.compute_wire_status(docs), "green")

    def test_dangling_deep_in_chain_is_unknown_not_leaf_verdict(self):
        """A dangling link ANYWHERE in the chain denies -- even when the
        leaf itself would otherwise resolve to a perfectly fine record one
        hop closer."""
        docs = [evidence_doc("v1", wire="a->b", verdict="green", superseded_by="ghost"),
                evidence_doc("v2", wire="a->b", verdict="green", superseded_by="v1")]
        self.assertEqual(andon_core.compute_wire_status(docs), "unknown")

    def test_expiry_judged_on_head_only(self):
        """The superseded (non-head) record's own valid_until must not
        matter -- only the head's."""
        docs = [
            evidence_doc("head", wire="a->b", verdict="green"),
            evidence_doc("leaf", wire="a->b", verdict="green",
                         superseded_by="head", valid_until="2020-01-01"),
        ]
        self.assertEqual(andon_core.compute_wire_status(docs), "green")

    def test_expired_head_is_unknown_even_if_green(self):
        docs = [evidence_doc("only", wire="a->b", verdict="green", valid_until="2020-01-01")]
        self.assertEqual(andon_core.compute_wire_status(docs), "unknown")

    def test_future_valid_until_on_head_is_unaffected(self):
        docs = [evidence_doc("only", wire="a->b", verdict="green", valid_until="2099-01-01")]
        self.assertEqual(andon_core.compute_wire_status(docs), "green")

    def test_malformed_valid_until_on_head_fails_closed(self):
        docs = [evidence_doc("only", wire="a->b", verdict="green", valid_until="not-a-date")]
        self.assertEqual(andon_core.compute_wire_status(docs), "unknown")


if __name__ == "__main__":
    unittest.main(verbosity=2)
