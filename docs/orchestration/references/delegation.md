# Parallel dispatch and model tiering

A controller session dispatching subagents chooses two things at once: whether a set
of dispatches actually runs in parallel, and which model tier each one deserves. Both
disciplines come from superpowers' `dispatching-parallel-agents` and
`subagent-driven-development`, cross-checked against what werkstoff's own agents
declare. `composition.md` covers what happens once those dispatches share guard hooks.

## The only parallel primitive

There is no scheduler and no shared blackboard behind subagent dispatch. Parallelism
is a property of how the controller writes its own response, stated verbatim by
`dispatching-parallel-agents`:

> Multiple dispatch calls in one response = parallel execution. One per response =
> sequential.

Independence is a precondition the controller establishes before dispatching, not
something the runtime discovers or enforces — nothing checks that two dispatched
agents avoid touching the same file or state. Integration is equally manual: nothing
merges the agents' outputs; the controller reads each summary, checks for conflicts,
and reconciles the results itself after they return.

**Use parallel dispatch when:**
- three or more independent problems exist (different test files, different
  subsystems, different bugs)
- each problem can be understood without context from the others
- no shared state exists between the investigations

**Do not use parallel dispatch when:**
- the failures are related — fixing one might fix the others, so investigate together
  first
- full system state must be understood before any one piece makes sense
- the dispatched agents would edit the same files or use the same resources

Superpowers itself ships zero agents and zero commands across its 14 skills — it
supplies the discipline, not the dispatch mechanism. Every werkstoff agent named
below is dispatched through the same generic subagent primitive superpowers
describes; superpowers never gives a reader an agent name of its own to invoke.

##### Two independent audits, one dispatch

````prompt
"map the repo's real module boundaries, and separately check whether our git remotes
and CI config still agree, then report both"
````

> Two calls in the same response — `self-assess-stage-map` and
> `self-assess-ci-topology` — run in parallel because neither reads the other's
> output. A single call naming both, or two calls split across separate responses,
> would run sequentially instead.

## Writing the dispatch prompt

A dispatch that runs in parallel with others still has to succeed on its own — no
later step reconciles a vague brief. `dispatching-parallel-agents` names the same
handful of mistakes across real sessions:

- **Too broad.** "Fix all the tests" loses an agent in scope it cannot bound. "Fix
  agent-tool-abort.test.ts" gives it a single file to own.
- **No context.** "Fix the race condition" does not say where. Pasting the actual
  error messages and failing test names does.
- **No constraints.** An agent given no boundary may refactor code well outside its
  task. "Do NOT change production code" or "fix tests only" holds the line.
- **Vague output.** "Fix it" leaves the controller unable to tell what changed.
  "Return a summary of the root cause and what you changed" does not.

These four apply whether the dispatch is one of several running in parallel or the
only one in its response — parallel dispatch multiplies the cost of a vague prompt by
however many agents received the same vagueness.

## Which model for which workstream

`subagent-driven-development`'s Model Selection section grounds the tiering below —
nothing here is invented past what that section states.

| tier | use for | why |
|---|---|---|
| cheapest | mechanical work on one or two files with an exact spec; name and link verification | when the brief supplies exact values, the work is transcription plus testing — a cheap model handles that reliably |
| standard | integration and judgment tasks; reviewers; implementers working from a prose spec rather than exact values | turn count rises fast on the cheapest tier for anything beyond pure transcription, so a mid-tier floor cuts overall cost and wall-clock time |
| most capable | architecture and design tasks; the final whole-branch review | design judgment and broad-codebase understanding are exactly where a weaker model's mistakes are hardest to catch downstream |
| at least one tier above the stuck implementer | fix-loop escalation rounds | a loop that survives several resumes on the same model usually means that model cannot see its own problem — fresh eyes plus a capability bump in one move |

The rule that makes this table matter, quoted verbatim:

> Always specify the model explicitly when dispatching a subagent. An omitted model
> inherits your session's model — often the most capable and most expensive — which
> silently defeats this section.

And the reason the cheapest tier is not simply "always pick cheap":

> Turn count beats token price.

Wall-clock and context cost scale with how many turns a subagent takes, and the
cheapest models routinely take two to three times the turns on multi-step work —
costing more overall than a mid-tier model would have. The table's "standard" row
exists because of this, not despite it.

## Defaults werkstoff agents already declare

Grepping `^model:` across every `plugins/*/agents/*.md` file in this repository shows
what a reader would be overriding by specifying a model explicitly, rather than
leaving these agents' own defaults in place:

| plugin | agents | declared model |
|---|---|---|
| cli-scaffold | cli-scaffold-verifier | `sonnet` |
| compass | branch-proposer, instruction-candidate, reasoning-path | `sonnet` |
| cupertino | handbook-dimension-analyst, handbook-drift-auditor, handbook-remediator, handbook-verifier | `sonnet` |
| self-assess | arch-health-auditor, business-rules-miner, ci-topology-auditor, complexity-surveyor, convention-auditor, docs-drift-auditor, idiom-auditor, idiom-remediator, stage-mapper, transform-executor, ui-auditor | `inherit` (declared explicitly) |
| andon | andon-adjudicator, andon-challenger, andon-defender, andon-verifier | none declared |
| confab | agentic-reliability-auditor, assertion-auditor, confab-remediator, contract-auditor, dependency-auditor | none declared |
| codebase-consistency | align-executor, consistency-critic, equivalence-verifier, pattern-analyst, pattern-extractor | none declared |

Two rows read the same at runtime but say different things on the page: self-assess's
agents spell out `model: inherit`, while andon, confab, and codebase-consistency omit
the field entirely. Both resolve to the dispatching session's model — but only the
first row documents that choice; the other three rows are silent, and a reader
scanning their frontmatter for a model line finds nothing rather than a decision.
Dispatching one of these agent names directly, outside its owning skill's own Task
call (which may pass a different override), gets whatever this table lists, or the
session default where the row says "none declared."

## Rules that keep a parallel run from going sideways

- **Batch small same-shape work into ONE dispatch.** When several pieces of work are
  each a small, independent edit of the same kind — the same one-line fix, the same
  constant change, repeated across files — send the whole batch to a single subagent
  rather than dispatching one agent per trivial task. Reserve one-dispatch-per-task
  for work that needs its own judgment, its own tests, or its own review surface.
- **Hand artifacts over as file paths, not pasted text.** Everything pasted into a
  dispatch prompt, and everything a subagent prints back, stays resident in the
  controller's context for the rest of the session and gets re-read on every later
  turn. A brief, a report, or a diff belongs in a file the subagent reads, not in the
  dispatch prompt itself.
- **Keep a file ledger.** Conversation memory does not survive compaction. A
  controller that loses its place has been observed re-dispatching entire completed
  task sequences — the single most expensive failure this discipline names. Track
  progress in a ledger file, not only in an in-session todo list.
- **Wait in bounded stretches rather than polling.** Neither a short-timeout poll
  loop nor one silent, open-ended wait serves a long-running dispatch well. Waiting
  in bounded stretches, then posting one line of status and reconciling live children
  between stretches, keeps nearly all of a long wait's efficiency while guaranteeing
  a stuck or lost child gets noticed within minutes rather than at the end of a
  session.

## Anti-patterns

- **Dispatching parallel agents at related failures.** If fixing one failure might
  fix the others, investigating them in isolation wastes the parallel dispatch and
  risks each agent proposing a fix that conflicts with the others' assumptions.
- **Splitting work that shares state.** Two agents editing the same file, or
  depending on the same resource, will interfere with each other regardless of how
  cleanly the task looked split on paper.
- **Omitting the model.** An omitted model silently inherits the session's model —
  see the verbatim rule above — which defeats the entire tiering discipline without
  producing any error a reader would notice.
- **Asking one agent to both build and verify its own work.** This repository already
  separates the two roles rather than trusting a single agent's self-review:
  `self-assess-idiom-fix` and `self-assess-transform-execute` both hand off to
  `andon:andon-verify` explicitly without self-verifying, and `andon-verify`'s own
  tribunal strategy dispatches `andon-defender` and `andon-challenger` in parallel,
  each blind to the other's case and to any prior verdict. Building and verifying in
  the same dispatch collapses a check that exists specifically to catch what a
  generous self-review misses.
