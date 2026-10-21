#!/usr/bin/env python3
"""Tests for the P0 gate: ONE contract judge, decided by code.

The two-judge panel this replaced counted ``{"judge_id", "confirms"}`` votes. These
tests pin the three ways that shape let a P0 rule through, so none can come back:

* a vote of ``"no"`` is truthy, so ``all(votes)`` confirmed a rule a judge rejected;
* a repeated ``judge_id`` overwrote the first vote, so one judge counted as two;
* nothing distinguished "the judge said no" from "no judge ran at all" from "a judge
  abstained", and only the first of those was ever a refusal.

They also pin the new gate end to end: ``p0_panel.confirm_p0_rule`` decides,
``validators.validate_business_rules_summary`` refuses, and the rubric table in
``references/judge-rubrics.md`` is the one the code runs.

Run: python3 plugins/befund/scripts/lib/test_p0_panel.py
"""
from __future__ import annotations

import copy
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent
PLUGIN = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))
from lib import judge_contract, p0_panel, transform_routing, validators  # noqa: E402
from lib.errors import SelfAssessError  # noqa: E402

CLI = SCRIPTS / "befund_cli.py"
CRITERIA = [c["id"] for c in p0_panel.P0_RUBRIC["criteria"]]


def report(item="RULE-003", scores=(0.9, 0.9, 0.9), passes=(True, True, True), **over):
    raw = {
        "item": item,
        "criteria": [
            {"id": cid, "score": sc, "pass": ok, "evidence": f"src/billing/overdraft.py:58 {cid}"}
            for cid, sc, ok in zip(CRITERIA, scores, passes, strict=True)
        ],
        "abstain": False,
        "abstainReason": None,
    }
    raw.update(over)
    return raw


def rule(**over):
    r = {"id": "RULE-003", "priority": "P0", "confidence": "High", "citation": "src/billing/overdraft.py:58"}
    r.update(over)
    return r


def confirmed_rule(**over):
    return p0_panel.confirm_p0_rule(rule(**over), report())["rule"]


class ConfirmTests(unittest.TestCase):
    def test_all_criteria_passing_confirms(self):
        out = p0_panel.confirm_p0_rule(rule(), report())
        self.assertTrue(out["confirmed"])
        self.assertIsNone(out["downgrade_reason"])
        self.assertEqual(out["rule"]["p0_verdict"]["outcome"], "pass")
        self.assertEqual(out["rule"]["p0_verdict"]["rubric"], "befund-p0-rule@1")
        self.assertEqual(out["rule"]["p0_verdict"]["item"], "RULE-003")
        self.assertEqual(judge_contract.validate(out["rule"]["p0_verdict"]), [])

    def test_the_old_panel_confirmed_key_is_gone(self):
        out = p0_panel.confirm_p0_rule(rule(panel_confirmed=True), report())
        self.assertNotIn("panel_confirmed", out["rule"])
        self.assertNotIn("panel_confirmed", out)

    def test_verdict_is_uncalibrated(self):
        # The rubric has no calibration record, so no verdict may claim calibration.
        self.assertFalse(confirmed_rule()["p0_verdict"]["calibrated"])

    def test_no_string_does_not_confirm(self):
        # Old panel: "no" is truthy, so a judge rejecting the rule confirmed it.
        raw = report()
        raw["criteria"][0]["pass"] = "no"
        out = p0_panel.confirm_p0_rule(rule(), raw)
        self.assertFalse(out["confirmed"])
        self.assertEqual(out["rule"]["p0_verdict"]["outcome"], "abstain")
        self.assertEqual(out["rule"]["p0_verdict"]["abstainReason"], f"bad-pass:{CRITERIA[0]}")

    def test_a_judge_that_says_pass_false_fails(self):
        out = p0_panel.confirm_p0_rule(rule(), report(passes=(True, False, True)))
        self.assertFalse(out["confirmed"])
        self.assertEqual(out["rule"]["p0_verdict"]["outcome"], "fail")
        self.assertIn("logic-executes", out["downgrade_reason"])

    def test_low_score_fails_at_the_threshold_boundary(self):
        # pass flags all true: only the 0.7 threshold can fail this.
        self.assertTrue(p0_panel.confirm_p0_rule(rule(), report(scores=(0.9, 0.7, 0.9)))["confirmed"])
        below = p0_panel.confirm_p0_rule(rule(), report(scores=(0.9, 0.69, 0.9)))
        self.assertFalse(below["confirmed"])
        self.assertEqual(below["rule"]["p0_verdict"]["outcome"], "fail")

    def test_score_is_the_minimum_not_the_average(self):
        out = p0_panel.confirm_p0_rule(rule(), report(scores=(1.0, 1.0, 0.5), passes=(True, True, True)))
        self.assertFalse(out["confirmed"])
        self.assertEqual(out["rule"]["p0_verdict"]["score"], 0.5)

    def test_missing_verdict_does_not_confirm(self):
        out = p0_panel.confirm_p0_rule(rule(), None)
        self.assertFalse(out["confirmed"])
        self.assertEqual(out["rule"]["p0_verdict"]["outcome"], "abstain")
        self.assertEqual(out["rule"]["p0_verdict"]["abstainReason"], "verdict-missing")
        self.assertIn("verdict-missing", out["downgrade_reason"])

    def test_abstain_does_not_confirm(self):
        out = p0_panel.confirm_p0_rule(
            rule(), {"item": "RULE-003", "criteria": [], "abstain": True, "abstainReason": "file not found"}
        )
        self.assertFalse(out["confirmed"])
        self.assertEqual(out["rule"]["p0_verdict"]["outcome"], "abstain")
        self.assertEqual(out["rule"]["p0_verdict"]["abstainReason"], "judge:file not found")

    def test_an_abstain_that_also_lists_passing_criteria_still_does_not_confirm(self):
        raw = report(abstain=True, abstainReason="unsure")
        out = p0_panel.confirm_p0_rule(rule(), raw)
        self.assertFalse(out["confirmed"])
        self.assertEqual(out["rule"]["p0_verdict"]["criteria"], [])

    def test_two_judge_reports_cannot_double_confirm(self):
        # The old API took a list of judges and let one id stand in for two. A list
        # is not a report, and the two-element shape confirms nothing.
        out = p0_panel.confirm_p0_rule(rule(), [report(), report()])
        self.assertFalse(out["confirmed"])
        self.assertEqual(out["rule"]["p0_verdict"]["abstainReason"], "verdict-missing")

    def test_a_fail_beside_an_undecidable_criterion_names_only_the_failure(self):
        # verdict@2: a failed criterion fails the rule whatever is undecidable, and the
        # downgrade reason names the failure, not the criterion nobody could decide.
        raw = report(scores=(0.2, None, 0.9), passes=(False, None, True))
        out = p0_panel.confirm_p0_rule(rule(), raw)
        self.assertFalse(out["confirmed"])
        self.assertEqual(out["rule"]["p0_verdict"]["outcome"], "fail")
        self.assertIn(CRITERIA[0], out["downgrade_reason"])
        self.assertNotIn(CRITERIA[1], out["downgrade_reason"])

    def test_an_undecidable_criterion_does_not_confirm(self):
        out = p0_panel.confirm_p0_rule(rule(), report(scores=(0.9, None, 0.9), passes=(True, None, True)))
        self.assertFalse(out["confirmed"])
        self.assertEqual(out["downgrade_reason"], f"abstain: undecidable:{CRITERIA[1]}")

    def test_old_vote_shape_does_not_confirm(self):
        out = p0_panel.confirm_p0_rule(rule(), {"judge_id": "judge-a", "confirms": True})
        self.assertFalse(out["confirmed"])

    def test_a_duplicated_criterion_abstains(self):
        raw = report()
        raw["criteria"].append(copy.deepcopy(raw["criteria"][0]))
        out = p0_panel.confirm_p0_rule(rule(), raw)
        self.assertFalse(out["confirmed"])
        self.assertEqual(out["rule"]["p0_verdict"]["abstainReason"], f"duplicate-criterion:{CRITERIA[0]}")

    def test_a_missing_criterion_abstains(self):
        raw = report()
        del raw["criteria"][2]
        out = p0_panel.confirm_p0_rule(rule(), raw)
        self.assertFalse(out["confirmed"])
        self.assertEqual(out["rule"]["p0_verdict"]["abstainReason"], f"missing-criterion:{CRITERIA[2]}")

    def test_a_report_about_another_rule_abstains(self):
        out = p0_panel.confirm_p0_rule(rule(), report(item="RULE-999"))
        self.assertFalse(out["confirmed"])
        self.assertEqual(out["rule"]["p0_verdict"]["abstainReason"], "item-mismatch")

    def test_a_rule_without_an_id_cannot_be_judged(self):
        for bad in ({"priority": "P0"}, {"id": "", "priority": "P0"}, {"id": 7, "priority": "P0"}):
            with self.assertRaises(SelfAssessError):
                p0_panel.confirm_p0_rule(bad, report(item=""))

    def test_a_stale_p0_verdict_on_the_input_is_replaced(self):
        forged = confirmed_rule()
        out = p0_panel.confirm_p0_rule(forged, None)
        self.assertEqual(out["rule"]["p0_verdict"]["outcome"], "abstain")
        self.assertFalse(out["confirmed"])


class ValidatorTests(unittest.TestCase):
    def check(self, *rules):
        validators.validate("business_rules_summary", {"rules": list(rules)})

    def test_confirmed_p0_passes(self):
        self.check(confirmed_rule())

    def test_p1_needs_no_verdict(self):
        self.check({"id": "RULE-014", "priority": "P1"})

    def test_legacy_panel_confirmed_true_is_refused(self):
        with self.assertRaises(SelfAssessError) as ctx:
            self.check(rule(panel_confirmed=True))
        self.assertIn("RULE-003", str(ctx.exception))
        self.assertIn("p0_verdict", str(ctx.exception))

    def test_missing_verdict_is_refused(self):
        with self.assertRaises(SelfAssessError):
            self.check(rule())

    def test_abstain_and_fail_verdicts_are_refused(self):
        for raw in (None, report(passes=(True, False, True)), report(abstain=True, abstainReason="x")):
            with self.subTest(raw=raw):
                with self.assertRaises(SelfAssessError):
                    self.check(p0_panel.confirm_p0_rule(rule(), raw)["rule"])

    def test_a_verdict_for_another_rule_is_refused(self):
        stolen = confirmed_rule()["p0_verdict"]
        with self.assertRaises(SelfAssessError) as ctx:
            self.check(rule(id="RULE-004", p0_verdict=stolen))
        self.assertIn("RULE-003", str(ctx.exception))

    def test_a_verdict_from_another_rubric_is_refused(self):
        other = copy.deepcopy(confirmed_rule()["p0_verdict"])
        other["rubric"] = "befund-other-rule@1"
        with self.assertRaises(SelfAssessError):
            self.check(rule(p0_verdict=other))

    def test_a_hand_edited_outcome_is_refused(self):
        # An abstain rewritten to "pass" must not survive: validate() checks the
        # outcome follows from the criteria.
        forged = copy.deepcopy(p0_panel.confirm_p0_rule(rule(), None)["rule"]["p0_verdict"])
        forged["outcome"] = "pass"
        with self.assertRaises(SelfAssessError):
            self.check(rule(p0_verdict=forged))
        failed = copy.deepcopy(
            p0_panel.confirm_p0_rule(rule(), report(passes=(True, False, True)))["rule"]["p0_verdict"]
        )
        failed["outcome"] = "pass"
        with self.assertRaises(SelfAssessError):
            self.check(rule(p0_verdict=failed))

    def test_a_forged_self_consistent_verdict_is_refused(self):
        # Each forgery is well-formed per judge_contract.validate(), names the right
        # rubric and rule, and has outcome "pass"; only re-deriving it under THIS
        # rubric (p0_panel.refusal) catches it.
        base = confirmed_rule()["p0_verdict"]

        def forge(**over):
            f = copy.deepcopy(base)
            f.update(over)
            return f

        low = [dict(c, score=0.3) for c in base["criteria"]]
        forgeries = {
            "threshold 0.0": forge(threshold=0.0),
            "threshold 0.0 with sub-threshold scores": forge(threshold=0.0, score=0.3, criteria=low),
            "calibrated true without a calibration record": forge(calibrated=True),
            "invented criterion ids": forge(
                criteria=[dict(c, id=f"anything-{i}") for i, c in enumerate(base["criteria"])]
            ),
            "wrong decidedBy": forge(decidedBy="command"),
        }
        for name, forged in forgeries.items():
            with self.subTest(forgery=name):
                self.assertEqual(judge_contract.validate(forged), [])
                self.assertEqual(forged["outcome"], "pass")
                with self.assertRaises(SelfAssessError) as ctx:
                    self.check(rule(p0_verdict=forged))
                self.assertIn("judge_contract.decide", str(ctx.exception))

    # Spellings that READ as P0 once NFKC-folded with whitespace and format characters
    # removed. The validator must REFUSE each (it never stores one): a stored "p0"
    # would pass here and then slip past transform_routing's exact P0 comparison.
    P0_SPELLINGS = {
        "lower case": "p0",
        "leading space": " P0",
        "trailing space": "P0 ",
        "both spaces": " p0 ",
        "inner space": "P 0",
        "tab inside": "P\t0",
        "fullwidth digit": "P\uff10",
        "fullwidth letter": "\uff30" + "0",
        "fully fullwidth": "\uff30\uff10",
        "fullwidth lowercase": "\uff50\uff10",
        "trailing zero-width space": "P0\u200b",
        "leading zero-width joiner": "\u200dP0",
        "zero-width space inside": "P\u200b0",
        "word joiner": "P\u20600",
        "no-break space": "P\u00a00",
        "ideographic space": "\u3000P0\u3000",
        "newline": "P0\n",
    }

    def test_a_p0_spelling_is_refused_not_stored(self):
        for label, spelling in self.P0_SPELLINGS.items():
            with self.subTest(variant=label):
                for r in (rule(priority=spelling), confirmed_rule(priority=spelling)):
                    with self.assertRaises(SelfAssessError) as ctx:
                        self.check(r)
                    msg = str(ctx.exception)
                    self.assertIn("not exactly one of", msg)
                    self.assertIn("write exactly 'P0'", msg)
                    self.assertIn("canonical form", msg)

    def test_the_exact_canonical_p0_is_still_gated(self):
        with self.assertRaises(SelfAssessError) as ctx:
            self.check(rule())
        self.assertIn("unconfirmed", str(ctx.exception))
        self.check(confirmed_rule())

    def test_a_priority_outside_the_closed_set_is_refused(self):
        # A list, a number, None, a near-miss or an empty string is invalid, not
        # "something other than P0": none may reach the summary unjudged.
        for bad in (["P0"], ("P0",), 0, None, True, {"P0": 1}, "", " ", "P4", "P", "0", "PO", "P00", "P0P1",
                    "P0\x00", "high"):
            with self.subTest(priority=bad):
                with self.assertRaises(SelfAssessError) as ctx:
                    self.check(confirmed_rule(priority=bad))
                self.assertIn("priority", str(ctx.exception))
        with self.assertRaises(SelfAssessError):
            self.check({"id": "RULE-020"})  # no priority at all

    def test_every_priority_in_the_closed_set_is_accepted(self):
        for exact in ("P1", "P2", "P3"):
            with self.subTest(priority=exact):
                self.check({"id": "RULE-021", "priority": exact})

    def test_a_non_canonical_p1_to_p3_spelling_is_refused(self):
        for spelling in ("p1", "p2", " P3 ", "\uff30\uff12", "P 1"):
            with self.subTest(priority=spelling):
                with self.assertRaises(SelfAssessError) as ctx:
                    self.check({"id": "RULE-021", "priority": spelling})
                self.assertIn("not exactly one of", str(ctx.exception))

    def test_a_bare_boolean_or_string_verdict_is_refused(self):
        for bad in (True, "pass", {"outcome": "pass"}, []):
            with self.subTest(bad=bad):
                with self.assertRaises(SelfAssessError):
                    self.check(rule(p0_verdict=bad))

    def test_one_unconfirmed_rule_refuses_the_whole_summary(self):
        with self.assertRaises(SelfAssessError):
            self.check(confirmed_rule(), rule(id="RULE-007"))


class FlagP0BlockersTests(unittest.TestCase):
    def blockers(self, *rules):
        return transform_routing.flag_p0_blockers(list(rules))

    def test_a_low_confidence_exact_p0_blocks(self):
        low = rule(confidence="Low")
        self.assertEqual(self.blockers(low), [low])

    def test_a_high_confidence_p0_and_other_priorities_do_not_block(self):
        self.assertEqual(self.blockers(rule(confidence="High")), [])
        self.assertEqual(self.blockers({"id": "R", "priority": "P1", "confidence": "Low"}), [])

    def test_every_p0_spelling_at_low_confidence_still_blocks(self):
        # flag-p0-blockers reads a JSON list that may never have been validated, so it
        # folds the spelling itself instead of trusting an exact "P0".
        for label, spelling in ValidatorTests.P0_SPELLINGS.items():
            with self.subTest(variant=label):
                low = rule(priority=spelling, confidence="Low")
                self.assertEqual(self.blockers(low), [low])
                self.assertEqual(self.blockers(rule(priority=spelling, confidence="High")), [])

    def test_a_priority_that_is_not_a_string_does_not_crash(self):
        for bad in (None, 0, ["P0"], {"P0": 1}):
            with self.subTest(priority=bad):
                self.assertEqual(self.blockers({"id": "R", "priority": bad, "confidence": "Low"}), [])

    def test_the_cli_reports_a_spelled_p0_blocker(self):
        proc = subprocess.run(
            [sys.executable, "-B", str(CLI), "flag-p0-blockers", "--rules",
             json.dumps([rule(priority="p0", confidence="Low")])],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual([r["id"] for r in json.loads(proc.stdout)["blockers"]], ["RULE-003"])


class RubricDocTests(unittest.TestCase):
    doc = (PLUGIN / "references" / "judge-rubrics.md").read_text(encoding="utf-8")

    def test_rubric_is_valid(self):
        self.assertEqual(judge_contract.check_rubric(p0_panel.P0_RUBRIC), [])

    def test_doc_names_the_same_rubric_id_and_threshold(self):
        self.assertIn(f"`{p0_panel.RUBRIC_ID}`", self.doc)
        self.assertIn(f"Threshold `{p0_panel.P0_RUBRIC['threshold']}`", self.doc)

    def test_doc_table_is_the_rubric_the_code_runs(self):
        rows = re.findall(r"^\| `([a-z][a-z0-9-]*)` \| (.+?) \|$", self.doc, flags=re.MULTILINE)
        self.assertEqual(
            rows, [(c["id"], c["question"]) for c in p0_panel.P0_RUBRIC["criteria"]]
        )

    def test_vendored_copies_match_the_canonical_ones_when_present(self):
        canonical = PLUGIN.parent.parent / "tools" / "judge-contract"
        if not canonical.is_dir():
            self.skipTest("installed standalone: no canonical tools/judge-contract to compare")
        self.assertEqual(
            (canonical / "judge_contract.py").read_bytes(), (SCRIPTS / "lib" / "judge_contract.py").read_bytes()
        )
        self.assertEqual(
            (canonical / "judge-contract.md").read_bytes(), (PLUGIN / "references" / "judge-contract.md").read_bytes()
        )


class SpotCheckTests(unittest.TestCase):
    def test_samples_three_of_five_and_reports_uncalibrated(self):
        rules = [
            p0_panel.confirm_p0_rule(rule(id=f"RULE-00{i}"), report(item=f"RULE-00{i}"))["rule"]
            for i in range(1, 6)
        ]
        out = p0_panel.spot_check_verdicts(rules, 3)
        self.assertEqual([v["item"] for v in out["sampled"]], ["RULE-001", "RULE-003", "RULE-005"])
        self.assertEqual(out["of"], 5)
        self.assertFalse(out["calibrated"])

    def test_failed_and_abstained_verdicts_are_sampled_too(self):
        rules = [
            p0_panel.confirm_p0_rule(rule(id="RULE-001"), None)["rule"],
            p0_panel.confirm_p0_rule(rule(id="RULE-002"), report(item="RULE-002", passes=(False, True, True)))["rule"],
        ]
        out = p0_panel.spot_check_verdicts(rules, 3)
        self.assertEqual([v["outcome"] for v in out["sampled"]], ["abstain", "fail"])

    def test_no_verdicts_is_not_calibrated(self):
        out = p0_panel.spot_check_verdicts([{"id": "RULE-001", "priority": "P1"}])
        self.assertEqual((out["sampled"], out["of"], out["calibrated"]), ([], 0, False))


class CliTests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, "-B", str(CLI), *args], capture_output=True, text=True, check=False
        )

    def test_p0_confirm_pass_then_validate_artifact(self):
        proc = self.run_cli("p0-confirm", "--rule", json.dumps(rule()), "--verdict", json.dumps(report()))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = json.loads(proc.stdout)
        self.assertTrue(out["confirmed"])
        summary = json.dumps({"rules": [out["rule"]]})
        proc = self.run_cli("validate-artifact", "--kind", "business_rules_summary", "--file", summary)
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_p0_confirm_null_verdict_is_an_abstain_not_a_crash(self):
        proc = self.run_cli("p0-confirm", "--rule", json.dumps(rule()), "--verdict", "null")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = json.loads(proc.stdout)
        self.assertFalse(out["confirmed"])
        self.assertEqual(out["rule"]["p0_verdict"]["abstainReason"], "verdict-missing")

    def test_the_old_judges_flag_is_gone(self):
        proc = self.run_cli("p0-confirm", "--rule", json.dumps(rule()), "--judges", "[]")
        self.assertNotEqual(proc.returncode, 0)

    def test_validate_artifact_refuses_the_legacy_shape(self):
        summary = json.dumps({"rules": [rule(panel_confirmed=True)]})
        proc = self.run_cli("validate-artifact", "--kind", "business_rules_summary", "--file", summary)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("REFUSED", proc.stderr)

    def test_p0_spot_check_prints_the_sample(self):
        rules = json.dumps([confirmed_rule()])
        proc = self.run_cli("p0-spot-check", "--rules", rules)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = json.loads(proc.stdout)
        self.assertEqual(out["of"], 1)
        self.assertFalse(out["calibrated"])
        self.assertEqual(out["sampled"][0]["item"], "RULE-003")


if __name__ == "__main__":
    unittest.main()
