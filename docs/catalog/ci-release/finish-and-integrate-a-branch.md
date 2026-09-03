---
task: "Finish and integrate a development branch"
category: ci-release
summary: "How to integrate -- merge, rebase, or PR -- is a decision with a real wrong answer in this repo, not a formality to skip once the tests are green."
openingPrompt: "Implementation's done and tests pass -- audit the changed files first, then help me actually decide how this branch should get integrated (merge, rebase, or PR) rather than defaulting to whichever, and once it's in, verify the release artifact was actually produced and prove the release wire itself instead of trusting a green merge."
external: ["superpowers"]
beats:
  - skill: "confab:confab-code-change"
    why: "Changed-files-scoped and advisory only -- it never blocks the commit -- so it belongs before the integration decision, not after."
  - skill: "superpowers:finishing-a-development-branch"
    why: "Fires once implementation is complete and tests pass, to decide how to integrate -- merge, rebase, or PR is a real decision, and making it implicitly is how branches get integrated the wrong way."
    prompt: "implementation's done and tests pass -- help me decide how this branch should actually get integrated"
  - skill: "superpowers:verification-before-completion"
    why: "\"It merged\" and \"it produced the artifact\" are different claims, and only one of them is the one that matters."
  - skill: "andon:andon-verify"
    why: "The release wire itself, proved rather than assumed just because the merge succeeded."
grounding: "This repo's own tagging rule: .github/workflows/cicd.yml fires on any v*.*.* tag and always publishes tools/werkstoff-cli, so a bare tag on a plugin group triggers a spurious PyPI publish -- <group>-v... tags fire plugin-release.yml instead. An integration decision with a real, irreversible wrong answer."
dos:
  - "Run the changed-files audit before making the integration decision, not after."
  - "Decide deliberately how to integrate -- merge, rebase, or PR is a real decision in this repo, with a real wrong answer."
  - "Verify the artifact was actually produced, not just that the merge succeeded -- those are different claims."
  - "Prove the release wire itself with andon-verify rather than assuming it holds because the merge went through."
donts:
  - "Don't treat the integration method as a formality once tests are green -- merge, rebase, or PR is a decision with a real wrong answer here."
  - "Don't tag a plugin group without its prefix -- a bare tag fires the wrong release path and triggers a spurious PyPI publish."
  - "Don't accept 'it merged' as evidence that 'it produced the artifact' -- verify the second claim, not just the first."
---

<RecipeHeader />

How to integrate a finished branch -- merge, rebase, or PR -- is a decision with a real
wrong answer in this repo, not a formality to rubber-stamp once the tests are green. Run
the changed-files audit first, make the integration decision deliberately, then verify what
actually happened rather than what was supposed to happen, and prove the release wire itself
before trusting that a green merge means the release is real.

<RecipeBeats />
