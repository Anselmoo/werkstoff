#!/usr/bin/env python3
"""The check-summary examples in handbook-check's SKILL.md are valid under validators.py.

A SKILL.md example the validator rejects is a trap: followed literally, the PreToolUse
hook denies the write. This extracts every ```json block there that looks like a check
summary and validates it, so the two cannot drift apart again.

Usage: python3 plugins/cupertino/scripts/test_validators.py
Exit: 0 all passed, 1 otherwise.
"""

from __future__ import annotations

import copy
import json
import re
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import validators  # noqa: E402

SKILL = HERE.parent / "skills" / "cupertino-handbook-check" / "SKILL.md"
BLOCK = re.compile(r"```json\s*\n(.*?)\n\s*```", re.DOTALL)


def summary_examples():
    out = []
    for raw in BLOCK.findall(SKILL.read_text()):
        obj = json.loads(raw)
        if isinstance(obj, dict) and "findings" in obj:
            out.append(obj)
    return out


class SkillExamples(unittest.TestCase):
    def test_examples_found(self):
        examples = summary_examples()
        self.assertGreaterEqual(len(examples), 2, "expected a populated and a zero-findings example")
        self.assertTrue(any(e["findings"] for e in examples), "no populated example")
        self.assertTrue(any(not e["findings"] for e in examples), "no zero-findings example")

    def test_every_example_validates(self):
        for i, ex in enumerate(summary_examples()):
            with self.subTest(example=i):
                self.assertEqual(validators.validate_handbook_check_summary(ex), {"ok": True})

    def test_example_without_rule_is_rejected(self):
        populated = next(e for e in summary_examples() if e["findings"])
        for key in ("rule", "quotedLine", "title", "evidence", "suggestedFix"):
            bad = copy.deepcopy(populated)
            del bad["findings"][0][key]
            with self.subTest(missing=key), self.assertRaises(validators.ValidationError):
                validators.validate_handbook_check_summary(bad)

    def test_blank_rule_is_rejected(self):
        bad = copy.deepcopy(next(e for e in summary_examples() if e["findings"]))
        bad["findings"][0]["rule"] = "  "
        with self.assertRaises(validators.ValidationError):
            validators.validate_handbook_check_summary(bad)


class Experience(unittest.TestCase):
    def test_dashboard_wording_is_allowed(self):
        validators.check_zero_tech_nouns("You glance at a table of what changed on one screen")

    def test_other_tech_nouns_still_banned(self):
        with self.assertRaises(validators.ValidationError):
            validators.check_zero_tech_nouns("A database behind an api")


if __name__ == "__main__":
    unittest.main()
