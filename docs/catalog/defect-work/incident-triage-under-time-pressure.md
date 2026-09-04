---
task: "Triage an incident under time pressure"
category: defect-work
summary: "Work root cause fast but not skipped, fan out hypotheses in parallel, and refuse to close on a proxy signal."
openingPrompt: "Production is down -- work the root cause fast but don't skip it, send several investigators at once on the likeliest independent causes in the same dispatch rather than serially, and don't let me close this out until you can show the actual cause is gone, not just that the alert stopped."
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
grounding: "a red `plugin-checks.yml` blocking every open pull request in this repo at once: the triage move is parallel investigators across the fourteen `continue-on-error` steps, not a tribunal on any one of them."
dos:
  - "Work the root cause fast, but work it -- the pressure to skip this step is exactly what turns one incident into three."
  - "Send multiple investigators in the same dispatch message -- that's what makes them parallel under time pressure, not sequential."
  - "Show that the actual cause is gone before closing out, not just that the alert cleared."
donts:
  - "Don't reach for a speculative revert instead of root-causing under pressure -- that's how one incident becomes three."
  - "Don't serialize the investigation across separate dispatches when time is the constraint -- send them in one message."
  - "Don't reach for werkstoff's evidence-accumulating, gate-heavy skills here -- they're right for a fix that must hold and wrong for a page at 02:00."
  - "Don't close the incident on the alert clearing alone -- verify the cause is actually gone."
---

<RecipeHeader />

**No werkstoff fit — this is pure Superpowers.** Every werkstoff skill in the defect space
is evidence-accumulating and gate-heavy by design — exactly right for a fix that must hold
and exactly wrong for a page at 02:00. Force-fitting them here would be the catalog's
worst advice.

<RecipeBeats />
