---
task: "Rehearse a release path that has never succeeded"
category: ci-release
summary: "Rehearse an unexercised release path in a disposable worktree, since no wire-proving skill has evidence to route yet."
openingPrompt: "This release workflow has never actually run -- before we trigger it, generate everything that has to be true for it to succeed, write it up as a plan whose steps can survive a failed first attempt, rehearse it in an isolated worktree rather than the real branch, and then show me the artifact it was actually supposed to produce, not just that the workflow went green."
external: ["superpowers"]
beats:
  - skill: "superpowers:brainstorming"
    why: "The failure modes of an unexercised path are unknown, not undiscovered; they have to be generated."
    prompt: "this release workflow has never actually run. Before we trigger it, list everything that has to be true for it to succeed."
  - skill: "superpowers:writing-plans"
    why: "An untested release path is a multi-step task, and the steps must survive a failed first attempt"
  - skill: "superpowers:using-git-worktrees"
    why: "A rehearsal that mutates the real branch converts a dry run into an incident."
    prompt: "set up an isolated worktree so we can rehearse this release without touching the real branch"
  - skill: "superpowers:verification-before-completion"
    why: "\"It ran\" and \"it produced the artifact\" are different claims, and only the second matters."
    prompt: "don't tell me it worked because the workflow went green — show me the artifact it was supposed to produce"
grounding: "`.github/workflows/batch-release.yml` is `workflow_dispatch`-only and reaches the bump-and-tag loop through `workflow_call` into `auto-version-bump.yml`. That reuse path has a different trigger surface from the push path exercised on every merge, so its first real run is also its first test."
dos:
  - "Generate the unexercised path's failure modes before triggering it -- they're unknown, not undiscovered, and have to be worked out rather than assumed away."
  - "Write the rehearsal as a plan whose steps survive a failed first attempt."
  - "Rehearse in an isolated worktree -- mutating the real branch converts a dry run into an incident."
  - "Check for the actual artifact the workflow was supposed to produce, not just that it went green."
donts:
  - "Don't trigger an unexercised release path directly against the real branch -- rehearse it in a disposable worktree first."
  - "Don't treat 'it ran' as equivalent to 'it produced the artifact' -- those are different claims and only the second matters."
  - "Don't reach for andon-verify here -- it proves a wire from evidence the wire already produced, and an unexercised path has none to route."
---

<RecipeHeader />

**No werkstoff fit — this is pure Superpowers.** `andon-verify` proves a wire from
evidence that the wire has already produced. A release path that has never run has
produced no evidence to route, so there is nothing for it to prove; and no werkstoff skill
rehearses an unexercised path.

<RecipeBeats />
