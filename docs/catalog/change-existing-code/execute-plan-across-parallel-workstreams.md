---
task: "Execute a written plan across parallel workstreams"
category: change-existing-code
summary: "Genuine independence, derived from the dependency graph rather than assumed, decides what can run in parallel -- and mechanical and architectural dispatches are tiered deliberately where the cost matters."
openingPrompt: "Break this plan into independent workstreams -- tell me what actually depends on what, from the real dependency graph rather than how the plan happens to be laid out -- then dispatch everything that's genuinely parallel in one message, choosing a model tier per dispatch where the cost matters, and prove each workstream on its own rather than trusting the aggregate result."
external: ["superpowers"]
beats:
  - skill: "superpowers:executing-plans"
    why: "Execute in a separate session with review checkpoints -- checkpoints cannot be retrofitted onto a run that's already in flight."
  - skill: "zirkel:zirkel-decompose-chain"
    why: "Derives which workstreams are genuinely independent from the dependency graph rather than by guess; a workstream that waits on another's output is a sequential step wearing a parallel label."
    prompt: "break this plan into independent workstreams -- tell me what actually depends on what and what can truly run in parallel"
  - skill: "superpowers:subagent-driven-development"
    why: "Fresh implementer per task with review after each; recommends specifying the model explicitly when dispatching a subagent, since an omitted model inherits the session's, possibly most expensive, tier."
  - skill: "superpowers:dispatching-parallel-agents"
    why: "Multiple dispatch calls in one response is what parallel execution actually means here -- one per response is sequential, no matter the intent."
  - skill: "andon:andon-verify"
    why: "Per-workstream proof; a partial parallel result reads exactly like a complete one until something checks each wire on its own."
grounding: "This is where plugins/takt/hooks/hooks.json belongs in the telling: one PreToolUse hook (matcher Skill|Task|Agent|Write|Edit|MultiEdit, inert until .claude/takt.local.md exists) that denies a dispatch running ahead of its declared beat -- a hook, not a skill, so it is named here in prose and never appears in a beats: list."
dos:
  - "Derive which workstreams are genuinely independent from the dependency graph, not from how the plan happens to be laid out."
  - "Send every parallel dispatch in the same response -- one call per response runs sequentially regardless of intent."
  - "Choose the model tier per dispatch where the cost matters -- an omitted model inherits the session's, possibly most expensive, tier by design."
  - "Give each workstream its own andon-verify proof rather than letting the aggregate result inherit one shared verdict."
  - "Set up review checkpoints before the run starts -- they cannot be retrofitted onto a run already in flight."
donts:
  - "Don't treat a workstream that waits on another's output as parallel -- it's a sequential step wearing a parallel label."
  - "Don't split dispatches across multiple responses expecting parallel execution -- one call per response is sequential, no matter the intent."
  - "Don't fan out a dozen mechanical dispatches on an inherited expensive tier without noticing -- tier them deliberately."
  - "Don't let a partial parallel result pass as complete -- it reads exactly the same until each wire is checked on its own."
---

<RecipeHeader />

What can run in parallel here is derived from the dependency graph, not assumed from
the plan's own layout — a workstream that waits on another's output is sequential work
wearing a parallel label. Mechanical and architectural dispatches are tiered
deliberately where the cost matters, and each workstream earns its own andon-verify proof rather than
inheriting one from the aggregate result.

<RecipeBeats />
