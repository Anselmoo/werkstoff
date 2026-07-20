---
name: compass-solve
description: Runs a complex, ambiguous, or multi-faceted task through compass's full Clarify -> Explore -> Decompose -> Execute -> Revise pipeline, composing the plugin's other 12 skills as pipeline stages instead of requiring the user to invoke them individually. Use when a task is genuinely large enough to need staged decomposition AND carries real ambiguity or multiple viable approaches worth weighing before committing — "solve this end-to-end, I'm not sure of the best approach", "plan this out and carry it out, here are the constraints", or a request that would otherwise mean chaining several compass-* skills by hand. Do not use for a single well-scoped question, a task with one obvious approach and nothing to decompose, or anything answerable directly — most requests do not need this skill; each of compass's other 12 skills stays independently invocable for a narrower job that doesn't warrant the full pipeline.
---

The plugin's primary entry point: given a complex/vague task, run it through
the composed pipeline the design spec calls for — matching
`code-modernization`'s phased-pipeline precedent (assess -> map ->
extract-rules -> ... ) rather than exposing `compass`'s 12 skills as an
independent, flat tool bag. The 5 steps below are internal composition, not a
menu — the user never picks "now run Tree-of-Thoughts"; they get a task
solved, and the technique-grounded skills are the mechanism underneath.

See `../../references/constraints.md` for the context-rot and
plausible-vs-verified constraints every phase below inherits — in particular,
every phase is instructed to read only the specific `SKILL.md` files it
actually needs, not the whole plugin's methodology at once.

## When to use

- The task is complex enough that it doesn't resolve in one direct answer,
  **and** either its scope is underspecified, or more than one genuinely
  different approach is worth weighing before committing.
- The user asks to "solve this end-to-end," "figure out the best way to do
  X and do it," or describes a task shaped like a small project rather than a
  single question.
- You'd otherwise be manually chaining `compass-clarify-scope` ->
  `compass-explore-branches` -> `compass-decompose-chain` -> per-stage
  execution -> `compass-draft-revise` by hand — this skill is exactly that
  chain, composed.

**Skip this skill** when the task is a single well-scoped question (answer it
directly, or reach for exactly one `compass-*` skill if one specific
technique-shaped failure mode applies — e.g. `compass-reason-verify` for a
multi-step calculation, `compass-ground-evidence` for a citation-heavy
answer). Running the full 5-step pipeline on a task that needs none of its
stages is the anchoring-on-process failure mode this plugin's own
big-picture note warns against — techniques patch specific failure modes,
they are not a default posture.

## The pipeline

| Step | Does what | Mechanism | Runs where |
|---|---|---|---|
| 1. Clarify | Raw task -> scoped problem statement | `compass-clarify-scope` | `solve-orchestrate.js` Mode A (Workflow) |
| 2. Explore | Scoped problem -> selected approach (skipped if only one approach is reasonable) | `compass-explore-branches` | This skill calls `compass-explore-branches` directly |
| 3. Decompose | Selected approach / scoped problem -> 2-5 stages with `dependsOn` | `compass-decompose-chain` | `solve-orchestrate.js` Mode B (Workflow) |
| 4. Execute | Each stage's own agent picks whichever of `compass-reason-verify` / `compass-investigate-dynamically` / `compass-ground-evidence` / `compass-calibrate-format` (or situationally `compass-map-relationships` / `compass-optimize-instruction`) its content needs | same 4+2 skills | `solve-orchestrate.js` Mode B, same call as Decompose |
| 5. Revise | Composed result -> scored + selectively revised against Step 1's criteria | `compass-draft-revise` | `solve-orchestrate.js` Mode B, same call |

## Step 0 — Load optional settings, if present

`compass` has no `output_dir` — every `compass-*` skill, including this
one, still returns its result into the conversation rather than writing
a persistent artifact, unlike `self-assess`/`confab`. But an optional
`.claude/compass.local.md` may exist in the repo you're working in (copy
`examples/compass.local.md` there to create one) — check for it before
proceeding:

- **Present**: its frontmatter overrides the corresponding default noted
  at each point in this pipeline — `branch_count`/`max_branch_count` in
  Step 2 (via `compass-explore-branches`'s own Step 0),
  `revision_threshold` in Step 3-5's Revise phase (via
  `compass-draft-revise`'s own Step 1), `always_render_trace` in the
  "Optional — view the reasoning trace interactively" section below, and
  `match_skill_set` in Step 3-5's Execute phase.
- **Absent**: every default below applies exactly as documented at each
  step — behavior is identical to before this file existed.

## Step 1 — Clarify

**Preferred — Workflow orchestration.** If the **Workflow tool** is
available in this session (this skill invocation is your authorization):

```
Workflow({
  scriptPath: "${CLAUDE_PLUGIN_ROOT}/workflows/solve-orchestrate.js",
  args: { pluginRoot: "${CLAUDE_PLUGIN_ROOT}", rawTask: "<the user's task, verbatim>", _contractVersion: "compass-contract-v1" }
})
```

This is a **Mode A** call (no `scopedProblem` in `args`): it runs only
Clarify, applying `compass-clarify-scope`'s methodology, and returns
`{scopedTask, knownFacts, flaggedUncertainties, successCriteria,
needsUserInput, blockingUncertainties}`.

- If `needsUserInput` is `true`: before pausing, offer to run
  `compass-verify-assumptions` on each `blockingUncertainties` entry —
  it may resolve one within its 3-step budget without needing a live
  answer. For any entry it leaves `still_unresolved`, **stop here and
  ask the user** — present the remaining `blockingUncertainties` (each
  with its `element`, `default_interpretation`, and `other_readings`)
  exactly as `compass-clarify-scope`'s own Step 3 requires for
  load-bearing uncertainties. This is why Clarify is a separate
  call from the rest of the pipeline: a Workflow script's dispatched agents
  run to completion autonomously and cannot pause mid-script for a live
  answer, so this script always returns immediately after Clarify rather
  than falling through to Decompose. Once the user answers, fold the answer
  into `scopedTask` yourself (or re-run this call with an amended `rawTask`)
  before continuing to Step 2.
- If `needsUserInput` is `false`: proceed to Step 2 with `scopedTask` and
  `successCriteria` in hand.

**Fallback** (no Workflow tool) — apply `compass-clarify-scope`'s own
methodology directly (its `SKILL.md` is plain in-conversation reasoning, no
agent/workflow needed), or invoke it as a skill. Its own Step 3 pause
behavior for load-bearing uncertainties applies exactly the same way here.

## Step 2 — Explore (skip when only one approach is reasonable)

Decide whether the scoped task actually has multiple genuinely viable
approaches worth weighing — the same gate `compass-explore-branches`'s own
description uses: "a task has multiple genuinely viable approaches and the
risk of anchoring on the first idea matters." See
`../../references/triage-tables.md#explore-gate` for this decision as a
table. If the task has one obvious
approach (a narrow bug fix, a single well-defined deliverable with no real
strategic fork), skip this step entirely — `selectedApproach` stays unset
and Step 3 consumes `scopedTask` directly, per `compass-decompose-chain`'s
own documented input contract ("a selected approach... **or** a scoped
problem statement directly").

When exploration is warranted, invoke the skill directly (never
`explore-branches-scan.js` from inside `solve-orchestrate.js` — no nested-
workflow primitive is available in this session; see the rationale comment
at the top of `solve-orchestrate.js` for why this is a skill-level call
instead of a workflow-level one):

Invoke `compass-explore-branches` with `scopedProblem: scopedTask`. Capture
its result's `selected` branch name and the branch's `description` (from its
`branches` array) as `selectedApproach` for Step 3. If the branches involve
entity/dependency/causal structure the scoped task references,
`compass-map-relationships` is available here too, per the design spec, to
ground a branch's feasibility claim in an actual traversal rather than a
guess.

After presenting the selected branch and its rationale, if 2 or more
branches scored closely (within a few total points of the winner),
offer `compass-negotiate-tradeoffs` as an optional next step — "I can
also try synthesizing a hybrid from the top branches, combining what
each does best, if that's useful before we commit." Never run it
automatically; only offer it, and only proceed to Step 3 with the
original winner's `description` as `selectedApproach` unless the user
asks for the hybrid instead.

## Step 3-5 — Decompose, Execute, Revise

Before this call, glob `${CLAUDE_PLUGIN_ROOT}/skills/compass-*/SKILL.md` to get
the actual list of skill ids present on disk (each matched directory name is
an id). `solve-orchestrate.js` has no filesystem access and cannot confirm
its own hardcoded `MODE_SKILLS`/`OPTIONAL_MODE_SKILLS` ids still have a
matching skill (see that file's "RENAME CHECKLIST" comment) — this glob,
passed in as `verifiedSkillIds`, is the verification layer that comment
calls for.

One **Mode B** call, once Step 1 (and Step 2, if it ran) are settled:

```
Workflow({
  scriptPath: "${CLAUDE_PLUGIN_ROOT}/workflows/solve-orchestrate.js",
  args: {
    pluginRoot: "${CLAUDE_PLUGIN_ROOT}",
    scopedProblem: "<scopedTask from Step 1>",
    successCriteria: <successCriteria from Step 1>,
    selectedApproach: "<selected branch's description from Step 2, or omit>",
    verifiedSkillIds: [<ids from the glob above, e.g. "compass-reason-verify", "compass-ground-evidence", ...>],
    matchSkillSet: [<ids from .claude/compass.local.md's match_skill_set, or omit if that file/field is absent>],
    _contractVersion: "compass-contract-v1"
  }
})
```

This single call runs all three remaining phases, none of which need a live
user pause:

- **Decompose** — one agent dispatch, pointed at
  `compass-decompose-chain/SKILL.md`, produces 2-5 stages (each with `id`,
  `name`, `inputContract`, `outputContract`, `dependsOn`), or a single
  synthesized `solve` stage if the task genuinely doesn't need decomposing.
- **Execute** — stages run in **topological-sort waves** over `dependsOn`
  (Kahn's algorithm, computed deterministically in plain JS): every stage in
  one wave has all of its `dependsOn` already satisfied by prior waves and
  is dispatched **in parallel** with the rest of that wave; waves themselves
  run in sequence. This is `dependsOn`'s single-source-of-truth meaning per
  `compass-decompose-chain/SKILL.md` — there is no separate parallel flag to
  read. Each stage's own dispatch decides, at the start of its own
  execution, which of `compass-reason-verify` / `compass-investigate-
  dynamically` / `compass-ground-evidence` / `compass-calibrate-format`
  (situationally also `compass-map-relationships` or
  `compass-optimize-instruction`, e.g. when a stage's deliverable is itself
  a recurring instruction) its content actually needs — never hardcoded per
  stage in advance. If a stage's output contract depends on an upstream
  assumption it needs confirmed before proceeding (rather than a full
  execution-mode methodology), `compass-verify-assumptions` is available
  to that stage's own dispatch too, alongside the modes above — bounded
  to 3 tool calls for exactly the one assumption in question. If
  `.claude/compass.local.md` sets `match_skill_set` (a list of
  `compass-*` skill ids), pass it through to the Mode B call as
  `matchSkillSet` — every stage then treats those ids as always-relevant
  in addition to whatever its own content calls for, never as a
  replacement for the stage-driven decision above.
- **Revise** — one agent dispatch, pointed at `compass-draft-revise/SKILL.md`,
  scores the composed result (every leaf stage's output — a stage no other
  stage depends on) against Step 1's `successCriteria` and revises only what
  scored at or below threshold.

**Known limitation — self-consistency inside Execute.** A stage dispatched
by the Execute phase is a single agent turn; it cannot itself fan out to
`reason-verify-scan.js`'s true 3-way parallel self-consistency tier (that
would be a second level of nested dispatch, which this session's tooling
doesn't support any more than nesting `explore-branches-scan.js` does). If a
stage's content genuinely needs that tier (a single-answer puzzle where an
early wrong assumption is costly, and the stakes justify three independent
passes), pull that stage out of the Mode B call: run `compass-reason-verify`
live, as its own top-level invocation (which *can* call
`reason-verify-scan.js`'s real Workflow), before or between Mode B calls,
and feed its result back in as part of `scopedProblem` or a stage's
`inputContract` rather than expecting the Execute-phase dispatch to do it
internally. This is a deliberate, documented gap, not a silent one.

**Fallback** (no Workflow tool) — apply `compass-decompose-chain`'s
methodology directly (plain in-conversation reasoning) to get `stages`;
compute the topological waves by hand using the same rule; for each wave,
spawn one subagent per stage via the Agent tool (or reason through the stage
yourself), each deciding its own execution mode the same way; apply
`compass-draft-revise`'s methodology to the composed leaf-stage output
against `successCriteria`.

## Present

Report, in this order:

1. **Scoped task** (Step 1's `scopedTask`), noting any non-blocking flagged
   uncertainties that were assumed rather than resolved.
2. **Explored approaches**, if Step 2 ran: the branch table (name,
   Feasibility/Impact/Risk/Total) and the selected branch with its rationale.
3. **Stage plan**: a table — `id | name | dependsOn | wave | modes used`.
4. **Composed result**, revised: the final `revisedResult` from Step 5, with
   the criteria score table and the `changes` list underneath it (per
   `compass-draft-revise`'s own "never present a revision without this
   list" discipline).

## `compass-optimize-instruction` is not a pipeline step

It is callable from within Step 4 (Execute) when a stage's own deliverable
is itself an instruction/prompt for a recurring task — one of the
situational skills a stage's dispatch may choose, alongside
`compass-map-relationships`. It never appears as a fixed phase of this
pipeline, and it is not a general prompt linter (see its own `SKILL.md`'s
Non-goal section) — a stage should reach for it only when it has (or can
elicit) representative test cases to score candidates against, not merely
because its deliverable happens to be text that reads like a prompt.

## Optional — view the reasoning trace interactively

If both of these exist under this plugin (they may be built by a separate,
parallel effort and not present yet — this step is skipped, never failed,
when they're absent):

- `${CLAUDE_PLUGIN_ROOT}/assets/reasoning-trace-viewer.html`
- `${CLAUDE_PLUGIN_ROOT}/references/render_trace.py`

...render the composed pipeline — Step 3-5's `dag` field (returned by
`solve-orchestrate.js`'s Mode B call: `{stages: [{id, name, inputContract,
outputContract, dependsOn, wave, modesUsed}], waves}`) as a DAG: stages and
their `dependsOn` edges. `render_trace.py` takes the JSON on **stdin**, not
as a CLI argument (checked directly against that script — unlike
self-assess-stage-map's renderer, compass has nothing written to disk to
point it at):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/references/render_trace.py" \
  "${CLAUDE_PLUGIN_ROOT}/assets/reasoning-trace-viewer.html" <output-path> <<'JSON'
<the dag object from solve-orchestrate.js's result, verbatim JSON>
JSON
```

`compass` has no `output_dir` convention (see Step 0) — pick a path in the
current working directory (e.g. `compass-trace.html`) or ask the user where
to put it. Present this as one optional closing line — "the reasoning trace
is available interactively at `<output-path>`, if you'd like to see how the
pipeline branched" — **never** as a required step; the pipeline's result in
Step "Present" above is already complete without it.

If `.claude/compass.local.md` sets `always_render_trace: true`, skip the
offer-and-wait — render it directly once the pipeline's Present step is
done, and mention where it was written. This still isn't a required
step in the sense that a missing viewer/renderer file is a silent skip,
never a failure; it only changes whether the user has to ask for it.

## Relationship to other compass skills

Every phase's methodology is owned by its corresponding skill's own
`SKILL.md` — this skill and `solve-orchestrate.js` apply that methodology
via agent prompts that point at the real file, they never reimplement it.
Each of the 12 skills stays independently invocable outside this pipeline
for a narrower job: reach for `compass-clarify-scope` alone to scope a task
without solving it, `compass-explore-branches` alone to compare a few
options, `compass-reason-verify`/`compass-ground-evidence`/
`compass-calibrate-format`/`compass-investigate-dynamically` alone for a
single reasoning task with one clear failure-mode signal, and so on — this
skill exists for the case where a task needs several of them, composed, not
as the only sanctioned entry point into the plugin.
