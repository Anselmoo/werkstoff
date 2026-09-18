# `workflow.json` — the compiled workflow spec

This is the **coded handoff**. Every later phase reads it; nothing in arbeitsplan re-derives its
contents from prose.

## Why this file is a schema and not a description

**Contents** — [why a schema](#why-this-file-is-a-schema-and-not-a-description) · [location](#location) · [schema](#schema) · [worked instance](#worked-instance) · [the six-phase shape](#the-six-phase-shape-on-the-workflow-backend) · [rejections](#rejections-at-compile-time) · [migrating from 1](#migrating-from-schemaversion-1)

`docs/plugin-benchmark-phase2-results.md` measured **9 of 11** skill-to-skill chains in this
repository failing their handoff *despite a real schema existing upstream*. The single chain that
passed did so for one reason, quoted from that document:

> `andon-propose`'s entire JSON output is copied byte-for-byte into `andon-verify`'s dispatch
> prompt — the one place in the plugin where a handoff is coded, not just documented.

So: a phase consumes `workflow.json` by reading the file, not by being told about it. A skill that
describes the spec in prose instead of loading it is the defect this schema exists to prevent.

## Location

`analysis/arbeitsplan/<runId>/workflow.json`, written by `arbeitsplan-compile`.

## Schema

| key | type | required | meaning |
|---|---|---|---|
| `schemaVersion` | `"2"` | yes | bumped only on a breaking change; a reader that does not recognise it **refuses**, never guesses. `"1"` is refused by name, with the migration in the message |
| `runId` | string | yes | `ap-<YYYY-MM-DD>-<4 hex>`. Also the takt marker namespace. Charset: `[A-Za-z0-9._-]+`, no `/`, no `..` |
| `problem` | object | yes | see below |
| `writeScope` | string[] | yes | fnmatch globs. **Never empty** — an empty scope is rejected at compile, not treated as "anything" |
| `budget` | object | yes | `totalDispatches` (int > 0), `wallClockMinutes` (int > 0) |
| `phases` | object[] | yes | 1..12 phases, see below |
| `delegates` | object[] | no | optional cross-plugin beats (compass et al.) |
| `backend` | object | yes | `{kind, why[], acknowledgedGaps[]}` — see below |

### `backend`

A bare string recorded *which* backend and never *why*, and nothing read it. The object is the
decision, and `arbeitsplan-backend` is the skill that makes it
(`references/backend-selection.md` holds the table).

| key | type | meaning |
|---|---|---|
| `kind` | `"in-session"` \| `"matrix"` \| `"workflow"` | the execution backend |
| `why` | string[] | **closed vocabulary**, one id per decision-table row. Each id names the kinds it can justify, and a `why` that selects a different kind is rejected: `edited-this-session`, `does-it-fire`, `tier-is-the-variable` → matrix; `writes-shared-tree` → matrix or in-session; `runtime-fanout-width`, `script-sequence` → in-session; `fixed-graph-returns-data`, `context-exceeds-session` → workflow |
| `acknowledgedGaps` | string[] | `workflow` **requires** `"workflow-tool-unhooked"`: no PreToolUse hook in this repo matches the Workflow tool, so its dispatches are unattributed. Choosing it means saying so |

### `problem`

| key | type | meaning |
|---|---|---|
| `statement` | string | the scoped problem, one paragraph |
| `shape` | `"change"` \| `"question"` | **`"question"` is a refusal**: compile emits an `out-of-scope-reasoning` record pointing at `compass:compass-solve` and writes no phases |
| `acceptance` | object[] | `{id, criterion, check}`. `check` is a shell command that exits 0 on pass. At least one entry, and **at least one with a non-null `check`** — a spec whose every criterion is unverifiable is rejected |

### `phases[]`

| key | type | meaning |
|---|---|---|
| `id` | string | unique within the run |
| `kind` | `"fanout-redundant"` \| `"fanout-blind"` \| `"fanout-readonly"` \| `"single-writer"` | determines who may hold Write |
| `pattern` | string | an id from `references/patterns.md`. Unknown id ⇒ **reject**, never improvise |
| `fanOut` | int | 1..16. Required for every `fanout-*` kind |
| `modelTier` | `"haiku"` \| `"sonnet"` \| `"opus"` | **always explicit** — an omitted tier inherits the session's model and silently defeats tiering (`docs/orchestration/references/delegation.md`) |
| `mode` | `"auto"` \| `"plan"` | **always explicit**, for the `modelTier` reason: an inherited plan mode turned four builders into UNMEASURED cells in the run that motivated this key. A `plan` phase must write `none`, and is never dispatched by the workflow backend — `run.js` halts before it and returns `pending_plan_node` |
| `writes` | `"none"` \| `"worktree"` \| `"shared"` | **always explicit**. `fanout-readonly` and `fanout-blind` write `none`; `fanout-redundant` writes `worktree`; a `single-writer` may declare any. The `workflow` backend refuses `shared` |
| `agentType` | string | **required**, namespaced (`plugin:name`). Closes the single-writer hole: without it the session did that work inline, unattributed. Under `matrix` it must be **absent** — a cell is a fresh process, not a dispatch |
| `angles` | string[] | one per candidate for `fanout-redundant`; `length` must equal `fanOut`. This is how widening is expressed |
| `sources` | string[] | `map-reduce-disjoint` only: exactly `fanOut` partitions, pairwise distinct |
| `reDerive` | object | **required** on `map-reduce-disjoint`: `{samplePct: 1..100, seed: int}`. Under-extraction is that pattern's named failure; the sample is picked in code by `scripts/sample_rederive.py`, never by a subagent |
| `borrowGate` | object | `select-then-synthesize` only: `{mustBeatWinnerOn: [acceptance ids]}`. Without it the synthesizer lands the plain winner; with it, a borrowed hunk must beat the winner on a named criterion |
| `cannotCheck` | string[] | what this phase declares it cannot verify, **before** any candidate exists — declared later, it would be written by the party whose work it excuses |
| `breaker` | object | `{acceptNumerator, acceptDenominator, scope: "per-batch"}`. `scope` is **only** `"per-batch"` |
| `requires` | string[] | marker names that must exist under `.takt/<runId>/` first |
| `marker` | string | the marker this phase creates on genuine completion |

### `delegates[]`

`{plugin, skill, beat, optional}` — compiled into a takt beat rather than dispatched in prose.
`optional: true` means: if the plugin is absent from the session's skill listing, drop the beat,
use the bundled fallback, and say so plainly. Never fabricate the delegate's output.

## Worked instance

```json
{
  "schemaVersion": "2",
  "runId": "ap-2026-09-12-a3f1",
  "problem": {
    "statement": "Rate-limit the public search endpoint without changing its response shape.",
    "shape": "change",
    "acceptance": [
      { "id": "a1", "criterion": "429 after 60 req/min from one key", "check": "pytest -q tests/test_ratelimit.py" },
      { "id": "a2", "criterion": "existing search tests still pass",   "check": "pytest -q tests/test_search.py" },
      { "id": "a3", "criterion": "no new runtime dependency",          "check": "git diff --exit-code -- requirements.txt" }
    ]
  },
  "writeScope": ["src/api/search.py", "src/api/limits/**", "tests/test_ratelimit.py"],
  "budget": { "totalDispatches": 9, "wallClockMinutes": 25 },
  "phases": [
    {
      "id": "build",
      "kind": "fanout-redundant",
      "pattern": "best-of-n",
      "fanOut": 3,
      "modelTier": "sonnet",
      "mode": "auto",
      "writes": "worktree",
      "agentType": "arbeitsplan:candidate-builder",
      "angles": ["middleware-layer", "decorator-per-route", "reverse-proxy-config"],
      "breaker": { "acceptNumerator": 2, "acceptDenominator": 3, "scope": "per-batch" },
      "requires": [],
      "marker": "built"
    },
    {
      "id": "referee",
      "kind": "fanout-blind",
      "pattern": "blind-referee",
      "fanOut": 3,
      "modelTier": "sonnet",
      "mode": "auto",
      "writes": "none",
      "agentType": "arbeitsplan:candidate-referee",
      "breaker": { "acceptNumerator": 2, "acceptDenominator": 3, "scope": "per-batch" },
      "requires": ["built"],
      "marker": "refereed"
    },
    {
      "id": "land",
      "kind": "single-writer",
      "pattern": "select-then-synthesize",
      "modelTier": "sonnet",
      "mode": "auto",
      "writes": "shared",
      "agentType": "arbeitsplan:synthesizer",
      "requires": ["refereed"],
      "marker": "landed"
    }
  ],
  "delegates": [
    { "plugin": "compass", "skill": "compass-explore-branches", "beat": "branches-explored", "optional": true }
  ],
  "backend": { "kind": "in-session", "why": ["writes-shared-tree"], "acknowledgedGaps": [] }
}
```

## The six-phase shape on the workflow backend

The shape that motivated v2 — INVENTORY haiku×4 map-reduce-disjoint, CONTRACT opus×1 plan,
BUILD sonnet×3 best-of-n, REFEREE sonnet×3 blind-referee, SYNTHESIZE sonnet×1
select-then-synthesize, ADJUDICATE opus×1 plan — compiles for `backend.kind: "workflow"` exactly
as `compile_spec.py --selftest`'s `SIX` fixture does. Three consequences are the point:

- **No landing phase.** Every phase returns data (`writes` is `none` or `worktree`); the synthesized
  diff is landed afterwards, in-session, by `land_candidate.py`, where the hook can see it.
- **Two plan-node stops.** CONTRACT and ADJUDICATE are `mode: "plan"`, so `run.js` returns
  `pending_plan_node` before each; the session runs that phase and re-launches from the next one.
  With a run-scope lock open, plan mode has no legal move — so the stop is structural, not advice.
- **INVENTORY carries `sources` and `reDerive`.** Four partitions, and a seeded sample of each
  extraction re-derived before CONTRACT reads it.

## Rejections at compile time

A spec is **not written** if any of these hold. Each is a refusal with the offending key named, never
a default silently supplied:

- `problem.shape == "question"` — emit `out-of-scope-reasoning`, point at `compass:compass-solve`
- `schemaVersion` is not `"2"` (`"1"` is refused by name, with the migration)
- `writeScope` empty or absent
- no acceptance criterion carries a runnable `check`
- a `phases[].pattern` not present in `references/patterns.md`
- `angles.length != fanOut` on a `fanout-redundant` phase
- `modelTier`, `mode` or `writes` absent on any phase
- `agentType` absent or un-namespaced (except under `matrix`, where it must be absent)
- a `writes` value its `kind` does not allow, or a `plan` phase that writes
- `requires` naming a marker no earlier phase creates (a dangling dependency)
- a marker created by two phases
- more than 12 phases
- `budget.totalDispatches` less than the sum of every phase's `fanOut`
- `backend` not an object; `backend.why` empty, outside the vocabulary, or selecting another kind
- `backend.kind == "workflow"` with a `writes: "shared"` phase, or without `"workflow-tool-unhooked"` acknowledged
- `map-reduce-disjoint` without `reDerive`, or with `sources` that are not `fanOut` distinct partitions
- `borrowGate` on any pattern but `select-then-synthesize`, or naming an unknown acceptance id

**Never infer a missing gating value.** Reject and surface it: a halt that depends on a value the
compiler invented is not a halt.

## Migrating from `schemaVersion` 1

1. `"backend": "in-session"` → `"backend": {"kind": "in-session", "why": ["writes-shared-tree"], "acknowledgedGaps": []}` — pick the `why` from `references/backend-selection.md`.
2. Every phase gains `mode` (`"auto"` unless it is a planning phase) and `writes` (`worktree` for builders, `none` for referees, `shared` for an in-session landing).
3. Every phase gains `agentType`. A `single-writer` landing phase that had none is `arbeitsplan:synthesizer`.
