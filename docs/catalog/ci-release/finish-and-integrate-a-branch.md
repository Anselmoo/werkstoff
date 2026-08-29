---
task: "Finish and integrate a development branch"
category: ci-release
summary: "How to integrate -- merge, rebase, or PR -- is a decision with a real wrong answer in this repo, not a formality to skip once the tests are green."
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
---

How to integrate a finished branch -- merge, rebase, or PR -- is a decision with a real
wrong answer in this repo, not a formality to rubber-stamp once the tests are green. Run
the changed-files audit first, make the integration decision deliberately, then verify what
actually happened rather than what was supposed to happen, and prove the release wire itself
before trusting that a green merge means the release is real.
