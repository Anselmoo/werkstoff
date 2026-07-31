---
name: compass-solve
description: >-
  Runs the full compass pipeline — Clarify -> Explore (conditional) -> Decompose
  -> Execute -> Revise — for a task that is complex/ambiguous AND needs staged
  decomposition AND carries real ambiguity or multiple viable approaches worth
  weighing. Use when a request is too big or too underspecified to answer in one
  shot: "solve this properly", "work through this step by step", "this is
  complex, break it down and do it", or any multi-faceted task where jumping
  straight to an answer would anchor on the wrong interpretation or approach.
  Not for simple, well-specified, single-step tasks.
---

# compass-solve

Compose the five phases in order. Each phase is a distinct compass skill; this
skill orchestrates them and **enforces the pipeline invariants in code** via the
guard CLI. Never skip a guard call — its non-zero exit is the enforcement.

`GUARD="python3 ${CLAUDE_PLUGIN_ROOT}/scripts/compass.py"`

## Preferred path: the workflow

When the Workflow tool is available, run the whole pipeline through
`${CLAUDE_PLUGIN_ROOT}/workflows/solve.js` (args: `{ task, multipleApproaches?,
requestedBranches?, maxBranchCount?, successCriteria?, priorClarify?, priorExplore? }`).
It computes Kahn waves, enforces phase order, and pauses on blocking uncertainty —
all in code. Prefer it.

**Workflow scripts have no filesystem access**, so every reuse check must happen
before you invoke it — the script runs to completion in one shot; it cannot pause
partway to ask you to look something up.
1. `echo '{"raw_task":"<task>"}' | $GUARD state-find - --output-dir .compass`. If
   `found` is true and `state.phase` is `Clarify` or later, that's your
   `args.priorClarify` (pass `state.clarify` through unchanged).
2. Only if step 1 found a reusable Clarify run do you already know
   `state.clarify.scoped_task` before invoking the workflow — if so, run
   `state-find` a second time with that text as `raw_task`. If it finds an
   `Explore`-phase match, that's your `args.priorExplore` (pass `state.explore`
   through unchanged).
3. If step 1 found nothing, Clarify will run fresh inside the workflow and you
   cannot know `scoped_task` in advance — pass no `priorExplore` in that case and
   accept that Explore-reuse only works for the workflow path when Clarify was
   also reused. (The Manual path doesn't have this limitation, since it can check
   again after Clarify actually runs.)

Never invent a `priorClarify`/`priorExplore` value yourself — only pass through
exactly what `state-find` returned.

## Manual path (no Workflow tool)

Run the phases yourself, calling the guard between each. **MUST run in this order:
Clarify -> Explore (conditional) -> Decompose -> Execute -> Revise.**

### 1. Clarify
**First, check for a prior run** (rule: solve-reuses-prior-standalone-run) so a
task someone already scoped with `compass-clarify-scope` doesn't get redone blind:
`echo '{"raw_task":"<the task text>"}' | $GUARD state-find - --output-dir .compass`
- If `found` is `true` and the returned `state.phase` is `Clarify` or later, **reuse
  `state.clarify`** as this phase's result instead of invoking `compass-clarify-scope`
  — tell the user you're reusing a prior scoping run (cite its `run_id`), don't
  silently redo it and don't silently skip mentioning it either.
- Otherwise, invoke `compass-clarify-scope` fresh.

Then, whichever `clarify` object you now have (fresh or reused), validate it and get
the pause decision: `echo '<clarify-json>' | $GUARD clarify -`
- The result's `must_pause` is a first-class field. **If `must_pause` is true you
  MUST stop and wait for user input before Explore.** Do not silently adopt a
  default for a blocking uncertainty. Present the `blocking_uncertainties` and halt.

### 2. Explore (conditional)
- **Skip Explore entirely** if the scoped task has one obvious approach and no real
  strategic fork; pass the scoped task straight to Decompose.
- Otherwise, **first check for a prior run**, matching on `clarify.scoped_task` (the
  exact text Explore is about to be given, whether Clarify just ran fresh or was
  reused above):
  `echo '{"raw_task":"<clarify.scoped_task>"}' | $GUARD state-find - --output-dir .compass`
  If `found` is `true`, `state.phase` is `Explore` (or later), and `state.explore` is
  present, **reuse `state.explore`** instead of invoking `compass-explore-branches` —
  cite the reused `run_id` to the user. Otherwise invoke `compass-explore-branches`
  to pick an approach.

### 3. Decompose
Invoke `compass-decompose-chain`, then:
`echo '{"stages":[...]}' | $GUARD decompose -`
The guard enforces 2-5 stages, an entry point, no dangling deps, no cycles, and
returns the `waves` (topological order). A non-zero exit means the plan is invalid
— fix it, do not proceed.

### 4. Execute (topological waves)
Run stages in the `waves` returned by the guard: **stages in a wave run in
parallel; waves run sequentially** (Kahn's algorithm). For each stage, decide its
execution mode **at runtime from the stage's own content** — one of
`reason-verify`, `investigate-dynamically`, `ground-evidence`, `calibrate-format`
— never hardcode a mode in advance. Validate the dispatch:
`echo '{"stages":[{"id":"s1","mode":"ground-evidence","mode_decided_at":"runtime"}]}' | $GUARD stage-dispatch -`

### 5. Revise
Invoke `compass-draft-revise` on the composed result against the success criteria.

### Final check
`echo '{"phases_run":["Clarify","Decompose","Execute","Revise"]}' | $GUARD phase-order -`
(add `"Explore"` in position if it ran). A non-zero exit means the pipeline ran
out of order — a bug to fix, not to report as success.

## Persisting the run
To persist run state for a later `compass-summarize-trace`, use the guarded writer
(it enforces write scope and validates every gating field before writing):
`echo '<state-json>' | $GUARD state-write - --output-dir .compass --to runs/<id>/state.json`
This is the pipeline's own final, complete record — write it under a fresh `<id>`
even when Clarify/Explore reused an earlier standalone run above; the reused runs'
own state.json files are left in place as-is, not merged or deleted.

## Output
- scoped task result
- explored approaches (only if Explore ran)
- stage plan table + wave grouping
- composed result from all stages
- revised result with the 1-5 score table and the changes list
