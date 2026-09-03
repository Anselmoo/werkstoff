---
task: "Triage an incident under time pressure"
category: defect-work
summary: "Work root cause fast but not skipped, fan out hypotheses in parallel, and refuse to close on a proxy signal."
external: ["superpowers"]
beats:
  - skill: "superpowers:systematic-debugging"
    why: "The pressure to skip this step is what turns one incident into three."
    prompt: "production is down. Work the root cause fast, but work it — no speculative reverts."
  - skill: "superpowers:dispatching-parallel-agents"
    why: "Multiple dispatch calls in one response run in parallel; under time pressure that difference is the whole game."
    prompt: "send three investigators at once — one on the deploy, one on the config change, one on the upstream dependency. Same message, don't serialize them."
  - skill: "superpowers:verification-before-completion"
    why: "\"The alert cleared\" and \"the cause is gone\" are different claims."
    prompt: "before we close this out, show me the cause is actually gone — not just that the alert stopped"
grounding: "a red `plugin-checks.yml` blocking every open pull request in this repo at once: the triage move is parallel investigators across the eleven `continue-on-error` steps, not a tribunal on any one of them."
---

<RecipeHeader />

**No werkstoff fit — this is pure Superpowers.** Every werkstoff skill in the defect space
is evidence-accumulating and gate-heavy by design — exactly right for a fix that must hold
and exactly wrong for a page at 02:00. Force-fitting them here would be the catalog's
worst advice.

<RecipeBeats />
