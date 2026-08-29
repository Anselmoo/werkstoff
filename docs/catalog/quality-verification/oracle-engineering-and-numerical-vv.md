---
task: "Do oracle engineering and numerical V&V"
category: quality-verification
summary: "Ground expected numeric values in an external source, since the code and the test can agree from the same misunderstanding."
external: []
beats:
  - skill: "compass:compass-ground-evidence"
    why: "An expected value with no citation is a second implementation, not an oracle."
    prompt: "where does each expected number in these tests come from? Cite a source for every one — no values derived from the code under test."
  - skill: "andon:andon-verify"
    why: "Strategy b is \"oracle-gap numerical V&V\" — named for exactly the gap between a numeric claim and an independent source of truth."
    prompt: "check whether this numeric claim is actually right — we have no independent oracle for it"
  - skill: "confab:confab-assertion-audit"
    why: "A tolerance wide enough to pass is a tolerance wide enough to hide the defect."
    prompt: "are these numerical assertions tight enough to fail if the computation were subtly wrong?"
grounding: "`tools/symbol-indexer/test_build_symbol_index.py` is the suite CI runs for the indexer; the oracle question is whether its expected index is derived independently or regenerated from the same `build_symbol_index.py` it is meant to check."
---

Numerical correctness has a distinct failure mode: the code and the test agree because
both were written from the same misunderstanding. The fix is an oracle the implementation
did not author.
