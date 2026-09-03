---
task: "Root-cause a bugfix from a tracked issue"
category: defect-work
summary: "Find where a reported behavior lives, reach root cause, write a failing test, then prove the fix adversarially."
external: ["superpowers"]
beats:
  - skill: "compass:compass-investigate-dynamically"
    why: "The location is unknown; a pre-planned file list cannot adapt to what each observation reveals."
    prompt: "I don't know where this behavior is implemented — go find it before we talk about fixing it"
  - skill: "superpowers:systematic-debugging"
    why: "Mandatory before proposing fixes; a fix without a cause is a guess with a diff."
    prompt: "work this to root cause. No fix, no patch, no workaround until the cause is proven."
  - skill: "superpowers:test-driven-development"
    why: "A regression test written after the fix passes for the wrong reason."
    prompt: "write the failing regression test for this bug first, then fix it"
  - skill: "andon:andon-verify"
    why: "Self-review is generous; the tribunal strategy dispatches defender and challenger blind to each other."
    prompt: "run the tribunal on this fix — I want a defender, a challenger, and someone who actually runs the checks"
grounding: "the failure mode recorded in `.github/workflows/plugin-checks.yml`: a `.gitignore` regression that silently drops a vendored file, leaving the artifact lock expecting a file that no longer exists — a bug whose symptom appears months later, at a hook denial, rather than where the cause lives."
---

<RecipeHeader />

The spine of this task is Superpowers: root cause before fix, failing test before code.
The werkstoff contribution is the search and the proof at either end.

<RecipeBeats />
