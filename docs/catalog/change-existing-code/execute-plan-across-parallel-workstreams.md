---
task: "Execute a written plan across parallel workstreams"
category: change-existing-code
summary: "Genuine independence, derived from the dependency graph rather than assumed, decides what can run in parallel -- and every dispatch, mechanical or architectural, carries an explicit model tier."
external: ["superpowers"]
beats:
  - skill: "superpowers:executing-plans"
    why: "Execute in a separate session with review checkpoints -- checkpoints cannot be retrofitted onto a run that's already in flight."
  - skill: "compass:compass-decompose-chain"
    why: "Derives which workstreams are genuinely independent from the dependency graph rather than by guess; a workstream that waits on another's output is a sequential step wearing a parallel label."
    prompt: "break this plan into independent workstreams -- tell me what actually depends on what and what can truly run in parallel"
  - skill: "superpowers:subagent-driven-development"
    why: "Fresh implementer per task with review after each; carries the rule verbatim: always specify the model explicitly when dispatching a subagent, since an omitted model silently inherits the most expensive tier."
  - skill: "superpowers:dispatching-parallel-agents"
    why: "Multiple dispatch calls in one response is what parallel execution actually means here -- one per response is sequential, no matter the intent."
  - skill: "andon:andon-verify"
    why: "Per-workstream proof; a partial parallel result reads exactly like a complete one until something checks each wire on its own."
grounding: "This is where plugins/takt/hooks/hooks.json belongs in the telling: one PreToolUse hook (matcher Skill|Task|Agent|Write|Edit|MultiEdit, inert until .claude/takt.local.md exists) that denies a dispatch running ahead of its declared beat -- a hook, not a skill, so it is named here in prose and never appears in a beats: list."
---

<RecipeHeader />

What can run in parallel here is derived from the dependency graph, not assumed from
the plan's own layout — a workstream that waits on another's output is sequential work
wearing a parallel label. Every dispatch, mechanical or architectural, carries an
explicit model tier, and each workstream earns its own andon-verify proof rather than
inheriting one from the aggregate result.

<RecipeBeats />
