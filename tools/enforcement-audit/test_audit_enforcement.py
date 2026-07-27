#!/usr/bin/env python3
"""Tests for the enforcement auditor.

Every case here is a regression from a bug the hand-check actually caught. A
static auditor can lie exactly as confidently as the regex oracles that wasted
a day of this pilot, so its own claims get pinned to executable assertions.

Run: python3 tools/enforcement-audit/test_audit_enforcement.py
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from audit_enforcement import ARG_SHAPE, audit  # noqa: E402

RULES = {
    "plugin": "t",
    "rules": [{
        "id": "reopen-limit",
        "section": "3",
        "must": "stop after N reopens",
        "state_terms": ["fixAttempts", "maxReopens", "reopen"],
        "prose_terms": ["reopen", "three times"],
    }],
}


class Fixture:
    """A throwaway plugin dir."""

    def __init__(self, files: dict[str, str]):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        for rel, body in files.items():
            p = self.root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(body)

    def verdicts(self):
        v, a = audit(self.root, RULES)
        return {x.rule_id: x for x in v}, a

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.tmp.cleanup()


class TestClassification(unittest.TestCase):
    def test_control_flow_guard_is_code(self):
        """The confab shape: a conditional on the rule's own state that diverts."""
        with Fixture({"workflows/loop.js":
                      "for (const e of entries) {\n"
                      "  if (e.fixAttempts >= maxReopens) return false\n"
                      "}\n"}) as f:
            v, _ = f.verdicts()
            self.assertEqual(v["reopen-limit"].verdict, "code")
            self.assertIn("loop.js:2", v["reopen-limit"].code_sites[0].file + ":"
                          + str(v["reopen-limit"].code_sites[0].line))

    def test_arg_validation_is_not_credited_as_enforcement(self):
        """The andon shape: a throw that validates an ARG whose name shares a term.

        andon-cycle-scan.js:24 is `if (!wireClaim && !Array.isArray(stageFiles))
        throw` — it contains 'wire' but enforces nothing about wires. Crediting
        it was the auditor's first bug.
        """
        with Fixture({
            "workflows/w.js":
                "if (!Number.isFinite(maxReopens) || maxReopens < 1) {\n"
                "  throw new Error('bad maxReopens')\n}\n",
            "skills/s/SKILL.md": "Nothing relevant here.\n",
        }) as f:
            v, argg = f.verdicts()
            self.assertEqual(v["reopen-limit"].verdict, "absent")
            self.assertTrue(argg, "the throw should still be reported as an arg guard")

    def test_punctuation_operator_is_detected_as_arg_shape(self):
        r"""Regression: `\b!==\b` never matches — no word char is adjacent to '!'.

        With the operators inside the \b group, `if (x !== null) { throw }`
        escaped the arg filter and was credited as rule enforcement.
        """
        self.assertTrue(ARG_SHAPE.search("symbolIndexPath !== null) "))
        self.assertTrue(ARG_SHAPE.search("mode === 'fix'"))
        self.assertTrue(ARG_SHAPE.search("typeof repoPath"))

    def test_arg_guard_with_punctuation_operator_not_credited(self):
        with Fixture({"workflows/w.js":
                      "if (maxReopens !== null) {\n"
                      "  throw new Error('bad')\n}\n"}) as f:
            v, argg = f.verdicts()
            self.assertEqual(v["reopen-limit"].verdict, "absent")
            self.assertTrue(argg)

    def test_prose_only_when_markdown_states_the_rule(self):
        with Fixture({"skills/s/SKILL.md":
                      "If the same wire reopens three times, escalate.\n"}) as f:
            v, _ = f.verdicts()
            self.assertEqual(v["reopen-limit"].verdict, "prose")

    def test_absent_when_neither(self):
        with Fixture({"skills/s/SKILL.md": "This plugin maps stages.\n"}) as f:
            v, _ = f.verdicts()
            self.assertEqual(v["reopen-limit"].verdict, "absent")

    def test_vendored_file_is_not_evidence(self):
        """build_symbol_index.py is byte-identical across plugins.

        Before exclusion, andon's wire-proof rule was reported as CODE at
        scripts/build_symbol_index.py:501 — the shared indexer. A file every
        plugin carries cannot be evidence about any one of them.
        """
        with Fixture({"scripts/build_symbol_index.py":
                      "if entry.fixAttempts >= maxReopens:\n    return False\n"}) as f:
            v, _ = f.verdicts()
            self.assertEqual(v["reopen-limit"].verdict, "absent")

    def test_test_fixtures_are_not_evidence(self):
        with Fixture({"test-fixtures/x/w.js":
                      "if (e.fixAttempts >= maxReopens) return false\n"}) as f:
            v, _ = f.verdicts()
            self.assertEqual(v["reopen-limit"].verdict, "absent")

    def test_code_beats_prose_when_both_present(self):
        with Fixture({
            "workflows/w.js": "if (e.fixAttempts >= maxReopens) return false\n",
            "skills/s/SKILL.md": "If the same wire reopens three times, escalate.\n",
        }) as f:
            v, _ = f.verdicts()
            self.assertEqual(v["reopen-limit"].verdict, "code")


class TestRulesFile(unittest.TestCase):
    def test_shipped_andon_rules_parse_and_cover_the_contract(self):
        p = Path(__file__).parent / "rules/andon.json"
        d = json.loads(p.read_text())
        ids = {r["id"] for r in d["rules"]}
        # §3's base rule + three stop conditions, and §9's v2 requirements.
        for required in ("andon-rule-base", "stop-1-wire-proof-failure",
                         "stop-2-authorization-ceiling", "stop-3-structural-contradiction",
                         "thrash-escalation-limit"):
            self.assertIn(required, ids)
        ceiling = next(r for r in d["rules"] if r["id"] == "stop-2-authorization-ceiling")
        # The contract requires the ceiling check at TWO checkpoints (§3.2).
        self.assertEqual(ceiling["checkpoints"], 2)
        for r in d["rules"]:
            self.assertTrue(r["state_terms"], f"{r['id']} has no state terms to match on")


if __name__ == "__main__":
    unittest.main(verbosity=2)
