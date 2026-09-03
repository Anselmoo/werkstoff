# Orchestrating werkstoff with superpowers and the official plugins

werkstoff's nine plugins, `obra/superpowers`, and Anthropic's official plugin set were
built independently, and they overlap far less than their descriptions suggest. This
catalog records how they compose in one session: which pieces own a whole task, which
drop into somebody else's workflow, and which handoffs are already wired so nobody
orchestrates them twice by hand.

## Three roles

Three different things are installed, and they stack rather than compete.

**werkstoff plugins are specialised inspectors and enforcers.** Seven of the nine
target one distinct failure mode and refuse to speak outside it — `andon` on
handoffs between stages that were never proven, `self-assess` on a repo that cannot
describe its own health, `confab` on assertions, contracts and dependency manifests
that look right and are not, `compass` on reasoning stages silently skipped under
pressure, `cupertino` on interfaces decorated instead of designed, `cli-scaffold` on
CLIs that are not production-grade, and `codebase-consistency` on the narrow case of
two or more valid, undocumented variants of the same convention coexisting. The
eighth, `takt`, ships no skills at all: it is one `PreToolUse` hook that denies an
edit or a dispatch running ahead of a beat the repository declared it depends on,
turning the sequencing this catalog documents into a refusal rather than a
suggestion.

**superpowers is process discipline.** It ships 14 skills, zero agents, zero commands,
and one `SessionStart` hook — so any agent, in any plugin's workflow, can execute it.
It supplies the loop shape (brainstorm, plan, TDD, request review, verify before
completion), never the domain judgement. It is authored at
`github.com/obra/superpowers` and distributed through the official marketplace; it is
not one of the 39 plugin directories inside `anthropics/claude-plugins-official`.
Nothing in it can be invoked as an agent or a slash command, and any instruction to do
so is wrong.

**The Anthropic-internal plugins ship named, tool-scoped agents that a command
orchestrates.** `pr-review-toolkit` holds 6 agents behind one command, `feature-dev`
3 behind one, `code-modernization` 8 behind ten, and `claude-security` 7 behind none.
The agents are the reusable part; the command is the pipeline that happens to sequence
them.

They compose because they occupy different layers: werkstoff supplies the inspector,
superpowers supplies the loop the inspector runs inside, and the official plugins
supply named reviewer agents to fill a beat neither of the other two covers.

## Orchestrators and leaves

This is the one distinction the rest of the catalog depends on.

An **orchestrator** is a fixed sequence whose middle steps read artifacts earlier steps
wrote. It cannot be dropped into another workflow, because a step invoked without its
predecessor's artifact either refuses or fabricates. Choose an orchestrator only when
it owns the whole task.

A **leaf** is dispatchable at any moment from a scoped prompt, carries no pipeline
state, and returns a result rather than advancing a ledger. Leaves are what compose
into another workflow's beats and gates.

### werkstoff

|Orchestrator|Why it cannot be dropped mid-flight|
|---|---|
|`andon-loop`|Owns and persists the OKF ledger; a pass is a traversal of the whole stream|
|`confab-cycle`|Re-runs audits to convergence under a pass cap enforced by `scripts/cycle_engine.py`|
|`self-assess-autopilot`|CHECK -> PLAN -> approval gate -> FIX+VALIDATE, each phase consuming the last|
|`self-assess-transform-brief`|Gated on `stage_graph.json`; degrades to "Ready-with-gaps" without it|
|`self-assess-transform-execute`|Applies exactly one human-authorized phase of `MODERNIZATION_BRIEF.md`|
|`compass-solve`|Clarify -> Explore -> Decompose -> Execute -> Revise as one fixed pipeline|
|`cupertino-handbook-fix`|Applies mechanical findings from a prior `cupertino-handbook-check` pass|
|`/consistency-map`, `/consistency-canonize`, `/consistency-brief`, `/consistency-align`, `/consistency-verify`|Every one reads `analysis/<area>/` artifacts an earlier command wrote|
|`andon-status`, `confab-status`, `self-assess-status`|Report on what has already run; they have nothing to say outside their own pipeline (`/consistency-status` behaves the same way)|

Everything else in werkstoff is a leaf. That covers all of `compass`'s reasoning
skills, all of `confab`'s auditors, `cupertino`'s technique skills, `cli-scaffold`'s
paradigm and doctrine skills, `self-assess`'s finding skills, every `*-preflight`, and
every named agent across all nine plugins.

Two leaves deserve calling out by name, because they are usually assumed to be
pipeline-bound and are not. `andon-verify` states "Never write to the ledger" and
`andon-propose` states "never write to the ledger yourself -- `andon-loop` persists
this". Both therefore run standalone from a scoped prompt: `andon` does not have to be
adopted wholesale to be useful, and its adversarial tribunal is available as a
verification beat inside any other workflow.

### The official set

|Orchestrator|Leaves it sequences|
|---|---|
|`/modernize-*` (ten commands)|`legacy-analyst`, `business-rules-extractor`, `version-delta-analyst`, `architecture-critic`, `security-auditor`, `test-engineer` (plus `scaffolder` and `uplift-migrator`, which are not standalone)|
|`/review-pr`|`code-reviewer`, `code-simplifier`, `comment-analyzer`, `pr-test-analyzer`, `silent-failure-hunter`, `type-design-analyzer`|
|`/feature-dev`|`code-architect`, `code-explorer`, `code-reviewer`|
|`create-plugin`|`agent-creator`, `plugin-validator`, `skill-reviewer`|

The six `pr-review-toolkit` agents declare no `tools:` key, fetch no PR themselves, and
are diff-shaped — which is exactly what makes them droppable into a werkstoff review
gate. `claude-security` is the exception on the other side: it sets
`disable-model-invocation: true`, so the model can never propose it, and five of its
seven agents state they are not for direct invocation.

## The four beats

Most multi-plugin work fits the same four beats. Name leaves at each beat, and reach
for an orchestrator only when one of them owns the task outright.

**Inspect and research.** `compass-clarify-scope` before any work begins, then
`self-assess-stage-map` for the real import graph, `self-assess-arch-health`,
`compass-map-relationships` and `compass-ground-evidence` for grounding, and the
official `legacy-analyst` or `code-explorer` where the code is unfamiliar.
`cupertino-backwards` goes first in any design-shaped task — before `cupertino-focus`
or any other cupertino technique.

**Split into workstreams.** superpowers `brainstorming` then `writing-plans` produce
the plan; `compass-decompose-chain` produces the dependency order;
`compass-explore-branches` produces genuinely distinct options before one is picked;
`compass-negotiate-tradeoffs` settles the fork the plan cannot.

**Execute in parallel.** superpowers `dispatching-parallel-agents` supplies the only
parallel primitive that matters, verbatim: "Multiple dispatch calls in one response =
parallel execution. One per response = sequential." Pair it with
`subagent-driven-development`, `test-driven-development`, and `using-git-worktrees`
for isolation. Leaf work at this beat: `scaffold-cli` under the `cli-architecture`
doctrine, `cupertino-council` at UI build-time before any code is written, and
`self-assess-idiom-fix` for mechanical rewrites.

**Verify.** `andon-verify` proves one named wire through whichever of seven strategies
its type calls for; `confab-assertion-audit` asks whether the tests would catch a
mutation; `confab-contract-drift` checks contracts after a refactor; superpowers
`requesting-code-review` and `verification-before-completion` close the loop; and the
`pr-review-toolkit` agents cover the diff-shaped checks werkstoff has no equivalent
for, `silent-failure-hunter` and `type-design-analyzer` in particular.

## Worked examples

Naming leaves in prose is not the same as showing what to actually type. Three real
recipes from the [catalog](../catalog/index.md), quoted unedited, each pairing a
werkstoff leaf with a leaf from one of the other two sources named in this document's
title.

**superpowers, at the "Execute in parallel" beat** — from
[`execute-plan-across-parallel-workstreams`](../catalog/change-existing-code/execute-plan-across-parallel-workstreams):

````prompt
break this plan into independent workstreams -- tell me what actually depends on what
and what can truly run in parallel
````

That single ask dispatches `compass:compass-decompose-chain` to derive the split, then
hands each independent workstream to `superpowers:subagent-driven-development` and
`superpowers:dispatching-parallel-agents`, with `andon:andon-verify` proving each one
before it counts as done.

**`code-modernization`, at the "Inspect and research" beat** — from
[`same-stack-version-uplift`](../catalog/change-existing-code/same-stack-version-uplift):

````prompt
we're moving this codebase up a major version of the same stack. Which breaking
changes actually affect our code?
````

`code-modernization:version-delta-analyst` is dispatched directly — `modernize-brief.md`
sanctions exactly this, and the eight-stage pipeline around it would refuse without
artifacts this task has no reason to produce. `self-assess:self-assess-code-idiom` then
judges idioms against the version this repo actually targets, and
`self-assess:self-assess-idiom-fix` applies only the mechanical fixes.

**`pr-review-toolkit:code-simplifier`, at the "Verify" beat** — from
[`audit-against-documented-conventions`](../catalog/quality-verification/audit-against-documented-conventions):

````prompt
extract the discrete, checkable rules this repo's own documentation states, and audit
the code against them
````

`code-simplifier` runs last in that recipe, deliberately: it simplifies the now-aligned
code only after `self-assess` has audited the documented rules and
`codebase-consistency` has canonized the undocumented ones, so nothing gets simplified
twice.

## What is already wired

Three handoffs exist in the skill definitions. Orchestrating them by hand duplicates
work and can double-apply a fix.

- `self-assess-autopilot` hands FIX+VALIDATE to `andon:andon-loop` once its approval
  gate passes, and never edits source itself. Without the `andon` plugin installed it
  reports that the plan is ready and stops.
- `self-assess-idiom-fix` and `self-assess-transform-execute` both declare their own
  changes unverified and hand off to `andon:andon-verify` — or `andon-loop` for a
  ledger-recorded proof — rather than self-verifying.
- `self-assess-autopilot`'s `autopilot-confab-optional` rule attempts confab's audit
  skills only when confab actually appears in the session's skill listing, reports
  "confab not installed" plainly when it does not, and never fabricates confab-shaped
  findings to fill the gap.

## Reading this catalog

The entry point stops here. Each reference below covers one decision a session
actually has to make.

- [the prompt catalog](../catalog/index.md) — the task-indexed prompt catalog: what to
  say, per task shape, to get the right combination dispatched.
- [`references/routing.md`](references/routing.md) — which of the four overlapping
  pipelines owns a task, and which brief must not be signed alongside it.
- [`references/gates.md`](references/gates.md) — the approval, verification and hook
  gates each family enforces, and where they collide.
- [`references/delegation.md`](references/delegation.md) — model tiering and dispatch
  shape for parallel subagent work.
- [`references/hazards.md`](references/hazards.md) — a catalog of composition
  hazards: what breaks when several hook-bearing plugins share a session.
- [`references/pairings.md`](references/pairings.md) — the pairing-indexed
  companion to the task catalog above: which two skills combine, and why.
- [`references/claude-md-block.md`](references/claude-md-block.md) — a paste-in
  `CLAUDE.md` block that encodes these routing rules for a repo.

For the standards that govern the plugin definitions themselves rather than their
composition, see [`../plugin-authoring/README.md`](../plugin-authoring/README.md).
