---
name: compass-decompose-chain
description: Breaks a selected approach (from compass-explore-branches) or a scoped problem (from compass-clarify-scope, or given directly for simpler tasks) into a 2-5 stage pipeline, each stage carrying an explicit input contract, output contract, and a dependsOn field marking its data dependency on other stages. Use this once an approach is settled and before execution begins, whenever a task is complex enough to need more than one distinct, checkable step but its stages can be planned upfront (contrast with compass-investigate-dynamically, for stages that can only be discovered step by step).
---

Break a selected approach into a verifiable multi-stage pipeline. This
skill generalizes two techniques: DSP's decompose-retrieve-synthesize
structure (`dsp.prompt.md`) — break a task into sub-units that can each
be resolved independently, then combine — and prompt-chaining's staged
pipeline (`prompt-chaining.prompt.md`) — each stage produces an
independently verifiable artifact that feeds the next stage exactly, no
implicit context carried forward. Plain skill: no agent, no workflow
file — this is in-conversation reasoning.

Source techniques (vendored locally, no external repo dependency):
`../../references/knowledge/dsp.md` and
`../../references/knowledge/prompt-chaining.md` — see `../../references/knowledge/index.md`.

See `../../references/constraints.md` for the context-rot and
plausible-vs-verified constraints every stage contract should respect
(keep each input contract minimal; never mark a stage's output verified
until it actually is).

## Input

Either:
- A **selected approach** from `compass-explore-branches`'s output
  (`{name, description, rationale}` for the winning branch), or
- A **scoped problem statement** directly — from `compass-clarify-scope`,
  or supplied as-is for a task simple enough to skip branch exploration.

## Step 1 — Decompose into stages

Split the approach into **2-5 stages**, each producing one distinct,
checkable deliverable — never a single monolithic step, and never more
granular than the task needs.

- If a stage's output can't be described without "and also," split it
  into two stages (prompt-chaining's discipline: one verifiable artifact
  per stage).
- If two candidate stages would consume the same upstream input and
  never combine their outputs, they are probably not sequential — check
  whether they are actually parallel-safe siblings (DSP's discipline:
  independent sub-questions resolved separately, combined only at
  synthesis).
- Fewer than 2 stages means the task didn't need decomposing — use
  whichever `compass-*` execution skill fits directly instead of this
  one. More than 5 usually means one stage is doing too much work (split
  it) or the task itself needs re-scoping via `compass-clarify-scope`
  first, rather than force-fitting it into a longer chain.

## Step 2 — Write each stage's contract

Contract: `compass-contract-v1` (see `plugin.json`'s `contractVersion` —
bump both together if this contract's shape changes incompatibly).

For every stage, define:

- **id** — a short kebab-case slug, unique within this decomposition
  (this is what other stages reference in `dependsOn`).
- **name** — a short label.
- **Input contract** — the exact fields/artifact this stage consumes,
  and its concrete source: either "scoped problem / selected approach"
  (for a stage with no upstream dependency) or "output of stage
  `<id>`," naming the specific fields consumed — never "context from
  earlier."
- **Output contract** — the exact fields/artifact this stage produces,
  described concretely enough that a downstream stage (or
  `compass-solve`) can consume it without re-deriving anything already
  decided.
- **dependsOn** — the array of stage ids this stage's input contract
  actually draws from (see below).

## The `dependsOn` field — the interface `compass-solve` reads

This is the exact shape another skill consumes, so its meaning is fixed:

- `dependsOn: string[]` — the ids of every stage whose output contract
  this stage's input contract requires.
- `dependsOn: []` (empty) means this stage's input is satisfied entirely
  by the original scoped problem / selected approach, never by another
  stage's output. It is **parallel-safe** with any other stage whose own
  `dependsOn` set is already satisfied at that point in execution.
- A non-empty `dependsOn` is a hard sequential dependency: the stage
  cannot start until every stage it names has completed and that
  stage's output contract is available to consume.
- Two stages are parallel-safe **with each other** when neither appears
  in the other's `dependsOn` and both of their own `dependsOn` sets are
  already satisfied — `compass-solve` derives this by grouping stages
  into execution "waves" via a topological sort on `dependsOn`, the same
  way `stage-map-scan.js` clusters deterministically after an agent-driven
  phase. There is deliberately no separate `parallelSafe` boolean field
  on each stage: a second field duplicating what `dependsOn` already
  encodes could drift out of sync with the dependency list itself.
  `dependsOn` is the single source of truth; parallel-safety is always
  derived from it, never stated redundantly.

## Step 3 — Validate before handing off

- Every id in a stage's `dependsOn` must reference a stage id actually
  defined in this decomposition — no dangling references.
- The `dependsOn` graph must be acyclic: walk each stage's dependency
  chain and confirm no stage transitively depends on itself.
- At least one stage must have `dependsOn: []` — a chain with no entry
  point can never start.
- Every field named in a stage's input contract must appear, verbatim or
  clearly mapped, in the output contract of one of the stages in its
  `dependsOn` (or in the original scoped problem/selected approach, if
  `dependsOn` is empty). An input contract that references something
  never actually produced upstream is DSP's "don't introduce facts not
  retrieved" failure mode, applied to stage design instead of fact
  retrieval.

## Step 4 — Present

Present the stages as a table — `id | name | input contract | output
contract | dependsOn` — in an order where every dependency appears
before its dependents. Follow it with one sentence naming the
parallel-safe wave grouping computed from `dependsOn` (e.g. "stages
`research-competitor-a` and `research-competitor-b` are parallel-safe;
`synthesize-comparison` and `draft-recommendations` are sequential").
This grouping is informational — `compass-solve`, not this skill, makes
the actual sequential-vs-parallel execution decision at run time, per
the design spec's orchestrator Execute phase.

## Worked example

Selected approach: "Interview-driven competitive analysis — gather
structured facts on each competitor independently, then synthesize a
comparative report with recommendations."

| id | name | input contract | output contract | dependsOn |
|---|---|---|---|---|
| `research-competitor-a` | Research Competitor A | selected approach's competitor list, item "Competitor A" | fact sheet `{pricing, features, marketPosition}` for Competitor A, each fact cited to a source | `[]` |
| `research-competitor-b` | Research Competitor B | selected approach's competitor list, item "Competitor B" | fact sheet `{pricing, features, marketPosition}` for Competitor B, each fact cited to a source | `[]` |
| `synthesize-comparison` | Synthesize comparison | fact sheets from `research-competitor-a` and `research-competitor-b` | comparison table (pricing/features/marketPosition across A and B) + 3 ranked differentiation opportunities | `[research-competitor-a, research-competitor-b]` |
| `draft-recommendations` | Draft recommendations | comparison table + differentiation opportunities from `synthesize-comparison` | 3-5 numbered recommendations, each tied to a specific opportunity from `synthesize-comparison` | `[synthesize-comparison]` |

`research-competitor-a` and `research-competitor-b` are parallel-safe
(both `dependsOn: []`, same wave). `synthesize-comparison` waits for
both; `draft-recommendations` waits for `synthesize-comparison`. This
mirrors DSP for the first two stages (independent per-entity retrieval,
no cross-dependency) and prompt-chaining for the last two (a strict
sequential pipeline where each stage's artifact is the next stage's
entire input).

## Relationship to other compass skills

- **Upstream**: `compass-explore-branches` (selected approach) or
  `compass-clarify-scope` (scoped problem) — either is consumed here as
  the starting contract.
- **Downstream**: `compass-solve`'s Execute phase runs these stages,
  choosing per-stage which of `compass-reason-verify` /
  `compass-investigate-dynamically` / `compass-ground-evidence` /
  `compass-calibrate-format` a stage's content actually needs — that
  choice is made at execution time by the orchestrating skill's own
  judgment, not decided or hardcoded here.
- **Distinction from `compass-investigate-dynamically`**: this skill is
  for tasks whose stages *are* knowable upfront. Use
  `compass-investigate-dynamically` instead when the action/tool
  sequence can only be discovered step by step, because each step's
  result determines the next action.
