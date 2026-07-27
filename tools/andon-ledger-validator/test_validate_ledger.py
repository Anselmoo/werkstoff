#!/usr/bin/env python3
"""Tests for the andon ledger validator. Stdlib unittest, no pytest needed.

Run: python3 tools/andon-ledger-validator/test_validate_ledger.py
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from validate_ledger import check_record, main, parse_record, validate  # noqa: E402

GAP_OK = '''---
type: gap
title: "rename uid to id"
description: "Public API field naming is inconsistent with call sites."
blast_radius: "local+reversible"
on_constraint: "false"
tags: ["kind:bug", "status:open"]
---

## Gap detail
- Stage: [[stages/api]]
'''

# The shape 65/66 real production records actually have: the gating value is
# present and correct to a human eye, and unreadable to every code path.
GAP_PROSE = '''---
type: gap
title: "rename uid to id"
description: "Public API field naming is inconsistent."
tags: ["kind:bug", "status:open"]
---

## Gap detail
- On constraint: false
- Proposal: rename the field. Strategy: e, Tier 3. Blast radius: local+reversible.
'''

GAP_ABSENT = '''---
type: gap
title: "rename uid to id"
description: "Public API field naming is inconsistent."
tags: ["kind:bug", "status:open"]
---

## Gap detail
- On constraint: false
- Proposal: rename the returned field across the public API.
'''

EVIDENCE_PROSE = '''---
type: evidence
title: "export list matches reality"
description: "Independent Tier 3 structural check."
resource: "web/src/contract/index.ts"
tags: ["strategy:e", "tier:3"]
---

## Evidence detail
- Verdict: green
- Non-overridable: false
'''


def codes(text: str) -> set[str]:
    return {f.code for f in check_record(text, "r.md")}


class TestGatingFields(unittest.TestCase):
    def test_frontmatter_declared_is_clean(self):
        self.assertEqual(codes(GAP_OK), set())

    def test_prose_only_is_migrate_not_absent(self):
        """The production defect: value readable by eye, invisible to code."""
        found = {f.code: f.severity for f in check_record(GAP_PROSE, "r.md")}
        self.assertEqual(found["blast_radius-in-prose"], "migrate")
        self.assertEqual(found["on_constraint-in-prose"], "migrate")
        self.assertNotIn("blast_radius-absent", found)

    def test_absent_everywhere_blocks(self):
        found = {f.code: f.severity for f in check_record(GAP_ABSENT, "r.md")}
        self.assertEqual(found["blast_radius-absent"], "block")

    def test_validator_never_supplies_a_value(self):
        """The whole point: an absent rating is reported, never inferred.

        A tool that filled this in would reproduce exactly the silent data
        repair this exists to catch — the next run would inherit a rating no
        human ever supplied.
        """
        for f in check_record(GAP_ABSENT, "r.md"):
            for enum_val in ("local+reversible", "hard-to-reverse", "shared-state-visible"):
                self.assertNotIn(f"= {enum_val}", f.detail)
                self.assertNotIn(f"assuming {enum_val}", f.detail)

    def test_invalid_enum_blocks(self):
        bad = GAP_OK.replace('"local+reversible"', '"probably-fine"')
        found = {f.code: f.severity for f in check_record(bad, "r.md")}
        self.assertEqual(found["blast_radius-invalid"], "block")

    def test_evidence_gating_fields(self):
        c = codes(EVIDENCE_PROSE)
        self.assertIn("verdict-in-prose", c)
        self.assertIn("non_overridable-in-prose", c)
        self.assertNotIn("resource-unused", c)


class TestRecordShape(unittest.TestCase):
    def test_multi_gap_title_blocks(self):
        rec = GAP_OK.replace('"rename uid to id"', '"CLAUDE.md: 2 contradictions"')
        found = {f.code: f.severity for f in check_record(rec, "r.md")}
        self.assertEqual(found["multi-gap-record"], "block")

    def test_singular_count_in_title_is_not_multi_gap(self):
        rec = GAP_OK.replace('"rename uid to id"', '"CLAUDE.md: 1 contradiction"')
        self.assertNotIn("multi-gap-record", codes(rec))

    def test_truncated_description_warns(self):
        sev = "x" * 130 + " and additionally SolverMeta is NOT amo"
        rec = GAP_OK.replace("Public API field naming is inconsistent with call sites.", sev)
        self.assertIn("description-truncated", codes(rec))

    def test_long_but_complete_description_is_clean(self):
        rec = GAP_OK.replace("Public API field naming is inconsistent with call sites.",
                             "y" * 140 + " which is fully stated.")
        self.assertNotIn("description-truncated", codes(rec))

    def test_unknown_type_warns_only(self):
        found = check_record('---\ntype: mystery\n---\nbody\n', "r.md")
        self.assertEqual([f.severity for f in found], ["warn"])


class TestParsing(unittest.TestCase):
    def test_hyphen_keys_normalize_to_underscore(self):
        front, _ = parse_record('---\ntype: gap\nblast-radius: "hard-to-reverse"\n---\nb\n')
        self.assertEqual(front["blast_radius"], "hard-to-reverse")

    def test_no_frontmatter_is_not_a_crash(self):
        front, body = parse_record("just a body\n")
        self.assertEqual(front, {})
        self.assertEqual(body, "just a body\n")


class TestModes(unittest.TestCase):
    """read tolerates a legacy ledger loudly; write demands well-formed records."""

    def _ledger(self, tmp: str, record: str) -> Path:
        root = Path(tmp) / "ledger"
        (root / "gaps").mkdir(parents=True)
        (root / "gaps" / "g1.md").write_text(record)
        return root

    def test_read_mode_tolerates_prose_but_write_mode_does_not(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._ledger(tmp, GAP_PROSE)
            self.assertEqual(main([str(root), "--mode", "read", "--format", "json"]), 0)
            self.assertEqual(main([str(root), "--mode", "write", "--format", "json"]), 1)

    def test_absent_blocks_in_both_modes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._ledger(tmp, GAP_ABSENT)
            self.assertEqual(main([str(root), "--mode", "read", "--format", "json"]), 1)
            self.assertEqual(main([str(root), "--mode", "write", "--format", "json"]), 1)

    def test_clean_ledger_passes_both_modes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._ledger(tmp, GAP_OK)
            self.assertEqual(validate(root), [])
            self.assertEqual(main([str(root), "--mode", "write", "--format", "json"]), 0)

    def test_missing_directory_is_exit_2(self):
        self.assertEqual(main(["/nonexistent/ledger", "--format", "json"]), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
