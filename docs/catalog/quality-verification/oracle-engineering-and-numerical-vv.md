---
task: "Do oracle engineering and numerical V&V"
category: quality-verification
summary: "Ground expected numeric values in an external source, since the code and the test can agree from the same misunderstanding."
openingPrompt: "Check where every expected numeric value in these tests actually comes from -- cite an independent source for each one, not a value derived from the code under test -- then prove any numeric claim we have no independent oracle for, and check whether the tolerances are actually tight enough to fail if the computation were subtly wrong."
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
dos:
  - "Cite an independent source for every expected numeric value -- a value derived from the code under test is a second implementation, not an oracle."
  - "Prove a numeric claim explicitly when no independent oracle exists for it yet."
  - "Check that tolerances are tight enough to actually fail on a subtly wrong computation."
donts:
  - "Don't derive an expected test value from the same code the test is meant to check -- that's a second implementation of the bug, not an oracle."
  - "Don't leave a numeric claim unproven just because the code and the test already agree -- they can agree from the same misunderstanding."
  - "Don't set a tolerance wide enough to pass regardless -- that's wide enough to hide the defect too."
---

# Do oracle engineering and numerical V&V

Numerical correctness has a distinct failure mode: the code and the test agree because
both were written from the same misunderstanding. The fix is an oracle the implementation
did not author.
