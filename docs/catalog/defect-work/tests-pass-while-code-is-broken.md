---
task: "Investigate tests that pass while the code is broken"
category: defect-work
summary: "Mutate the source and check whether the suite would actually notice, instead of trusting a green run."
external: ["claude-plugins-official"]
beats:
  - skill: "confab:confab-assertion-audit"
    why: "Proposes off-by-one, boundary-flip, and condition-negation mutations and judges whether any existing test catches them."
    prompt: "mutate this module — flip a boundary, negate a condition, shift an index — and tell me which mutations the tests would not catch"
  - skill: "pr-review-toolkit:pr-test-analyzer"
    why: "Coverage percentages are compatible with assertions that assert nothing."
    prompt: "review the tests on this branch for behavioral coverage, not line coverage — where are the real gaps?"
  - skill: "andon:andon-verify"
    why: "One of its seven strategies is verify-the-verifier — the right shape when the checker is what is suspect."
    prompt: "I don't trust this test suite. Verify the verifier before we trust anything it says."
grounding: "auditing `plugins/confab/scripts/test_cycle_engine.py` and `tools/enforcement-audit/test_audit_enforcement.py` for assertions whose expected value is the same hardcoded default the code falls back to when the real path never runs."
---

A green suite proves the tests ran, not that they would notice. The specific trap worth
naming: an assertion whose expected value brackets a hardcoded default, so the test passes
whether or not the logic under it ever executes.
