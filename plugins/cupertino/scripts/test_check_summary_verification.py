#!/usr/bin/env python3
"""handbook-check-summary refuses a finding that was not independently confirmed.

handbook-fix.js applies a finding only when `verification.verdict == "confirmed"`.
If the summary validator let the field be absent, a real summary would pass the
write hook and then make fix mode skip every finding without a word. The
validator is the producer-side half of the fail-closed gate.

Run: python3 plugins/cupertino/scripts/test_check_summary_verification.py
"""

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import validators

FINDING = {
    "file": "src/a.tsx",
    "line": 7,
    "severity": "Medium",
    "title": "inline style",
    "evidence": "src/a.tsx:7",
    "mechanical": True,
    "suggestedFix": "use a class",
    "verification": {"verdict": "confirmed"},
}


def summary(**over):
    finding = {**copy.deepcopy(FINDING), **over}
    return {"domain": "code", "generatedAt": "2026-10-20T00:00:00+00:00", "findings": [finding]}


class CheckSummaryVerification(unittest.TestCase):
    def test_confirmed_finding_is_accepted(self):
        self.assertEqual(validators.validate_handbook_check_summary(summary()), {"ok": True})

    def test_unconfirmed_shapes_are_refused(self):
        bad = [
            {"verification": None},
            {"verification": True},
            {"verification": "confirmed"},
            {"verification": {}},
            {"verification": {"verdict": "false_positive"}},
            {"verification": {"verdict": True}},
        ]
        for over in bad:
            with self.subTest(over=over), self.assertRaises(validators.ValidationError):
                validators.validate_handbook_check_summary(summary(**over))

    def test_absent_verification_is_refused(self):
        obj = summary()
        del obj["findings"][0]["verification"]
        with self.assertRaises(validators.ValidationError):
            validators.validate_handbook_check_summary(obj)

    def test_zero_findings_stays_valid(self):
        obj = summary()
        obj["findings"] = []
        self.assertEqual(validators.validate_handbook_check_summary(obj), {"ok": True})


if __name__ == "__main__":
    unittest.main()
