---
task: "Execute a written plan across parallel workstreams"
category: change-existing-code
summary: "Genuine independence, derived from the dependency graph rather than assumed, decides what can run in parallel -- and every dispatch, mechanical or architectural, carries an explicit model tier."
openingPrompt: "Break this plan into independent workstreams -- tell me what actually depends on what, from the real dependency graph rather than how the plan happens to be laid out -- then dispatch everything that's genuinely parallel in one message with an explicit model tier per dispatch, and prove each workstream on its own rather than trusting the aggregate result."
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
dos:
  - "Derive which workstreams are genuinely independent from the dependency graph, not from how the plan happens to be laid out."
  - "Send every parallel dispatch in the same response -- one call per response runs sequentially regardless of intent."
  - "Always specify the model explicitly per dispatch -- an omitted model silently inherits the session's, usually most expensive, tier."
  - "Give each workstream its own andon-verify proof rather than letting the aggregate result inherit one shared verdict."
  - "Set up review checkpoints before the run starts -- they cannot be retrofitted onto a run already in flight."
donts:
  - "Don't treat a workstream that waits on another's output as parallel -- it's a sequential step wearing a parallel label."
  - "Don't split dispatches across multiple responses expecting parallel execution -- one call per response is sequential, no matter the intent."
  - "Don't omit the model tier on a dispatch -- it silently inherits the most expensive tier instead of the one the task actually needs."
  - "Don't let a partial parallel result pass as complete -- it reads exactly the same until each wire is checked on its own."
---

<RecipeHeader />

What can run in parallel here is derived from the dependency graph, not assumed from
the plan's own layout — a workstream that waits on another's output is sequential work
wearing a parallel label. Every dispatch, mechanical or architectural, carries an
explicit model tier, and each workstream earns its own andon-verify proof rather than
inheriting one from the aggregate result.

<RecipeBeats />
