---
task: "Investigate tests that pass while the code is broken"
category: defect-work
summary: "Mutate the source and check whether the suite would actually notice, instead of trusting a green run."
openingPrompt: "This suite is green but I don't trust it -- mutate the source (flip a boundary, negate a condition, shift an index) and tell me which mutations it wouldn't catch, review the tests for real behavioral coverage rather than line coverage, and verify the verifier itself since it's the checker that's actually in question here."
external: ["claude-plugins-official"]
beats:
  - skill: "zeugnis:zeugnis-assertion-audit"
    why: "Proposes off-by-one, boundary-flip, and condition-negation mutations and judges whether any existing test catches them."
    prompt: "mutate this module — flip a boundary, negate a condition, shift an index — and tell me which mutations the tests would not catch"
  - skill: "zeugnis:zeugnis-mutation-harden"
    why: "Runs a real mutation tool on the module the audit flagged and writes the tests that kill what survives, each kill proven by applying its mutant."
    prompt: "run mutmut on this module and write the tests that kill the mutants that survive"
  - skill: "pr-review-toolkit:pr-test-analyzer"
    why: "Coverage percentages are compatible with assertions that assert nothing."
    prompt: "review the tests on this branch for behavioral coverage, not line coverage — where are the real gaps?"
  - skill: "andon:andon-verify"
    why: "One of its seven strategies is verify-the-verifier — the right shape when the checker is what is suspect."
    prompt: "I don't trust this test suite. Verify the verifier before we trust anything it says."
grounding: "auditing `plugins/zeugnis/scripts/test_cycle_engine.py` and `tools/enforcement-audit/test_audit_enforcement.py` for assertions whose expected value is the same hardcoded default the code falls back to when the real path never runs."
dos:
  - "Mutate the source with off-by-one, boundary-flip, and condition-negation changes, and check which ones the suite would miss."
  - "Review for behavioral coverage, not line coverage -- a high percentage is compatible with assertions that assert nothing."
  - "Verify the verifier itself when the suite, not the code, is what's actually suspect."
  - "When an estimate is not enough, run a real mutation tool on a fresh copy and report the untested mutants apart from the score."
donts:
  - "Don't trust a green suite as proof the tests would notice a regression -- it only proves the tests ran."
  - "Don't treat a high coverage percentage as evidence of real assertions -- it's compatible with tests that assert nothing meaningful."
  - "Don't write an assertion whose expected value is the same hardcoded default the code falls back to -- it passes whether or not the real path ever executes."
  - "Don't run a mutation tool in the working tree -- mutmut 3 writes mutants/ there and its apply rewrites the source file."
---

<RecipeHeader />

A green suite proves the tests ran, not that they would notice. The specific trap worth
naming: an assertion whose expected value brackets a hardcoded default, so the test passes
whether or not the logic under it ever executes.

<RecipeBeats />
