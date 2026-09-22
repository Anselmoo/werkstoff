# `workflow.json` — the compiled workflow spec

This is the **coded handoff**. Every later phase reads it; nothing in arbeitsplan re-derives its
contents from prose.

## Why this file is a schema and not a description

**Contents** — [why a schema](#why-this-file-is-a-schema-and-not-a-description) · [location](#location) · [schema](#schema) · [outputs and its checks](#outputs-and-its-checks) · [breaker and its checks](#breaker-and-its-checks) · [base and stacked fan-outs](#base-and-stacked-fan-outs-79) · [worked instance](#worked-instance) · [the six-phase shape](#the-six-phase-shape-on-the-workflow-backend) · [rejections](#rejections-at-compile-time) · [recorded-red validators](#recorded-red-validators-issues-77-74-75-79) · [migrating from 1](#migrating-from-schemaversion-1)

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
| `refereeOwned` | string[] | no | path globs written by a `referee-fixture` phase before any candidate exists, and subtracted from every fan-out phase's effective write scope (#77) — see below |
| `delegates` | object[] | no | optional cross-plugin beats (zirkel et al.) |
| `backend` | object | yes | `{kind, why[], acknowledgedGaps[]}` — see below |

### `refereeOwned`

An oracle, a fixture, or an acceptance artifact that the builders must be judged against but
must not author. Declared once, at spec level, as a list of path globs — **never** inferred
from what a phase happened to touch. Absent is legal; most specs need no such fixture.

Every `refereeOwned` path must be reachable through `writeScope` (else declaring it protects
nothing — `AP-REFOWNED-OUTSIDE-SCOPE`) and must be produced by a `referee-fixture` phase (else
it is declared but nothing ever writes it — `AP-REFOWNED-NO-PRODUCER`). Both are **recorded-red**
rejections; see [Recorded-red validators](#recorded-red-validators-issue-77) below.

The subtraction is computed in exactly one place, `land_candidate.subtract_referee_owned`, and
called from both ends: `compile_spec.py`'s `AP-REFOWNED-OUTSIDE-SCOPE` check (per path, against
`writeScope`) and `worktree_pool.py`'s `open` (against the whole scope, for every fan-out
phase's lock). A `writeScope` glob that overlaps a `refereeOwned` path or glob is dropped
**whole** — `fnmatch` has no negation, so there is no narrower pattern to hand back in its
place without inventing one, which this plugin refuses everywhere else. `land_candidate.py`
also refuses (citing `refereeOwned` by name) any candidate diff that touches one of these
paths directly, by `in_scope()` — independent of whether the lock's narrowed scope should
already have stopped it. `scripts/referee_owned.py` hashes each path once, at creation
(`record`, refused a second time for the same run), and re-checks it by content
(`verify`) — "delivering such an artifact immutably, so its identity is checkable rather than
asserted," in the issue's own words.

### `outputs` and its checks

`outputs` (#74) is a phase-level list of the paths that phase is expected to produce. It is
always checked at compile time — **no flag needed** — against the phase's **effective write
scope**: `land_candidate.in_scope(path, writeScope)` and, for a fan-out phase, `NOT
land_candidate.in_scope(path, refereeOwned)`. Those are exactly the two tests
`land_candidate.py` applies when it actually lands a diff, imported here rather than
re-derived, so compile time and landing time can never disagree about the same path:

- outside `writeScope` (any phase) → `AP-OUTPUT-OUTSIDE-SCOPE`, recorded-red
- inside `refereeOwned` (a fan-out phase only — `fanout-redundant`, `fanout-blind`,
  `fanout-readonly`) → `AP-OUTPUT-REFOWNED`, recorded-red
- on `referee-fixture` specifically, `outputs` must equal `refereeOwned` exactly (wave 1's
  shape rule, unchanged)

Two CLI flags read `outputs`, neither on by default:

- **`--dry-land`** prints one line per declared output, `DRYLAND <phaseId> <path>
  IN|OUTSIDE|REFOWNED`, computed with the same effective-scope logic above, then compiles as
  normal (same exit code a plain compile would give).
- **`--probe-checks`** is unrelated to `outputs` — it runs every `problem.acceptance[].check`
  once via `/bin/sh`, cwd = the process's own cwd, under a `--probe-timeout` (default 60s).
  It prints `PROBE <acceptanceId> <CLASS> exit=<n>` per check, `CLASS` one of `RAN`,
  `ABSENT-TARGET` (exit 127), `SYNTAX` (exit 2), `PERMISSION` (exit 126) or `TIMEOUT` (exit
  -1) — a check that ran and failed is still `RAN`. Any non-`RAN` check is rejected,
  `AP-CHECK-NOT-RAN`, recorded-red: a criterion nothing could execute cannot referee anything.
  **A plain compile — without `--probe-checks` — executes nothing**; probing is opt-in.

### `breaker` and its checks

`workflows/run.js` reads a fan-out phase's `breaker` unconditionally at dispatch time —
`ph.breaker || DEFAULT_BREAKER` (`{acceptNumerator: 2, acceptDenominator: 3}`) — and compares
it against the batch: `scoped.length * acceptDenominator < measured.length * acceptNumerator`
(`fanout-redundant`, line 401) or the equivalent for `fanout-readonly`'s acquisition check (line
339). Before #75, `compile_spec.py` never looked at `breaker` at all, so a permanently disabled
gate compiled clean. It is now validated wherever it appears on a phase, five checks, each a
recorded-red rejection (see below):

- **`AP-BREAKER-INCOMPLETE`** — `breaker` is present but not an object, or
  `acceptNumerator`/`acceptDenominator` is missing or not a plain `int` (a `bool` is **not** an
  int here — `true`/`false` are rejected by this rule, not silently coerced)
- **`AP-BREAKER-DISABLED`** — `acceptNumerator == 0`. The comparison becomes `x < 0`, which
  never trips: that is a disabled gate, not a threshold of zero
- **`AP-BREAKER-RATIO`** — the bound is `1 <= acceptNumerator <= acceptDenominator`
  (`acceptDenominator < 1`, `acceptNumerator < 0`, or `acceptNumerator > acceptDenominator` are
  each a violation; `acceptNumerator == 0` is caught by `AP-BREAKER-DISABLED` first)
- **`AP-BREAKER-SCOPE`** — `scope`, when present, must be exactly `"per-batch"`. Absent is legal
- **`AP-BREAKER-KIND`** — `breaker` is declared on a phase whose `kind` is not one of the three
  fan-out kinds (`fanout-redundant`, `fanout-blind`, `fanout-readonly`) — including
  `single-writer` and `referee-fixture` — because nothing in `workflows/run.js` ever compares a
  non-fan-out phase's result against a breaker

`workflows/run.js`'s own `DEFAULT_BREAKER` (`{acceptNumerator: 2, acceptDenominator: 3}`)
already satisfies `1 <= acceptNumerator <= acceptDenominator`, so the fallback a phase gets when
it declares no `breaker` at all is never itself a violation of the bound this section enforces.

### `base` and stacked fan-outs (#79)

A wave whose builders should start from a *prior* wave's refereed winner declares `base:
"<phaseId>"` on a `fanout-redundant` phase — only there; on any other `kind` it is
`AP-BASE-INVALID`. `base` must name an **earlier** `fanout-redundant` phase Q that some earlier
`fanout-blind` phase actually reviewed (required Q's marker), and this phase's own transitive
`requires` must reach that reviewer's marker in turn — a `base` is a **refereed winner**, never
an unjudged or unrelated one. Any of that failing is `AP-BASE-INVALID`, naming the phase and its
declared `base`. Under `backend.kind: "workflow"`, **any** `base` is rejected outright as
`AP-BASE-BACKEND`: `run.js`'s `isolation: "worktree"` creates every candidate worktree fresh
from HEAD, with no way to seed it from a promoted branch.

`worktree_pool.py create --spec S --phase P --count N` is what actually honours it: if `P`
declares `base: Q`, every worktree this call creates starts from branch
`arbeitsplan/<runId>/base/Q` instead of HEAD — and if that branch has never been promoted, the
command **refuses**, naming the branch, and creates nothing. `create --spec S --count N` with no
`--phase` (or a `--phase` whose phase carries no `base`) behaves exactly as before: from HEAD.
`worktree_pool.py promote --run R --phase Q --candidate cW` commits everything sitting in
`.arbeitsplan/R/cW` — untracked files included — and points `arbeitsplan/R/base/Q` at that
commit; this is the one seam a later `create --phase` reads. `worktree_pool.py destroy --run R`
leaves every `arbeitsplan/R/base/*` branch alone (a later wave may still stack on it); only
`destroy --run R --bases` also deletes them.

**`AP-SIBLING-INVISIBLE` (a `WARNING`, not a rejection)** catches the case `base` exists to
prevent: for every `fanout-redundant` phase P, walk its `requires` transitively over the marker
→ producing-phase map, stopping at (but still crediting) any `writes: "shared"` phase on the
way — a landed phase already carries everything before it into the shared tree, so nothing
beyond a landing is missing from a fresh worktree checked out after it. If that walk reaches
another `fanout-redundant` phase Q and P's own `base` chain (`base`, its `base`'s `base`, ...)
does not reach Q, then Q's candidates were never landed and P was never stacked on Q either — Q's
fan-out is invisible in P's fresh worktree, a builder made from HEAD, not from Q's winner. The
warning names **both** phase ids. A plain compile still prints it and still writes (exit 0);
`--strict` turns any `WARNING` into a rejection (exit 1). Warnings print whether or not the spec
was also rejected for something else. Only `fanout-redundant` phases are checked — a
`fanout-blind` referee or a `single-writer` synthesizer receives diffs as data, never a worktree
of its own, so there is nothing for either to be missing.

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
| `shape` | `"change"` \| `"question"` | **`"question"` is a refusal**: compile emits an `out-of-scope-reasoning` record pointing at `zirkel:zirkel-solve` and writes no phases |
| `acceptance` | object[] | `{id, criterion, check}`. `check` is a shell command that exits 0 on pass. At least one entry, and **at least one with a non-null `check`** — a spec whose every criterion is unverifiable is rejected |

### `phases[]`

| key | type | meaning |
|---|---|---|
| `id` | string | unique within the run |
| `kind` | `"fanout-redundant"` \| `"fanout-blind"` \| `"fanout-readonly"` \| `"single-writer"` \| `"referee-fixture"` | determines who may hold Write. `referee-fixture` (#77) is a single writer that runs before every fan-out phase and produces the spec's `refereeOwned` paths — never fanned out, always `writes: "shared"`, always `pattern: "calibrate-then-measure"` |
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
| `outputs` | string[] | optional, on **any** phase (#74): the paths this phase is expected to produce. Always statically checked, no flag needed — see [outputs and its checks](#outputs-and-its-checks) below. On `referee-fixture` specifically it is additionally a **shape check**, not a second declaration: when present it must equal the spec's `refereeOwned` exactly, so a fixture's declared output and what candidates are protected from touching can never disagree |
| `breaker` | object | `{acceptNumerator, acceptDenominator, scope: "per-batch"}`. **Validated (#75)** — see [`breaker` and its checks](#breaker-and-its-checks) below |
| `base` | string | optional, **only on `fanout-redundant`** (#79): an earlier `fanout-redundant` phase this one's worktrees are stacked on. **Validated** — see [`base` and stacked fan-outs](#base-and-stacked-fan-outs-79) below |
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
    { "plugin": "zirkel", "skill": "zirkel-explore-branches", "beat": "branches-explored", "optional": true }
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

- `problem.shape == "question"` — emit `out-of-scope-reasoning`, point at `zirkel:zirkel-solve`
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
- a `referee-fixture` phase with `fanOut`, a `pattern` other than `calibrate-then-measure`, an
  `outputs` that does not equal `refereeOwned`, or that comes after any fan-out phase
- `refereeOwned` present but empty, not a list of strings, declared with no `referee-fixture`
  phase to produce it (`AP-REFOWNED-NO-PRODUCER`, recorded-red), or naming a path `writeScope`
  never reaches (`AP-REFOWNED-OUTSIDE-SCOPE`, recorded-red)
- a phase's `outputs` naming a path outside `writeScope` (`AP-OUTPUT-OUTSIDE-SCOPE`,
  recorded-red), or a fan-out phase's `outputs` naming a path inside `refereeOwned`
  (`AP-OUTPUT-REFOWNED`, recorded-red)
- with `--probe-checks`: any `problem.acceptance[].check` that does not classify `RAN`
  (`AP-CHECK-NOT-RAN`, recorded-red) — never checked on a plain compile
- a phase's `breaker` that is not an object, or whose `acceptNumerator`/`acceptDenominator` is
  missing or not a plain `int` (`AP-BREAKER-INCOMPLETE`, recorded-red); has
  `acceptNumerator == 0` (`AP-BREAKER-DISABLED`, recorded-red); violates
  `1 <= acceptNumerator <= acceptDenominator` (`AP-BREAKER-RATIO`, recorded-red); declares a
  `scope` other than `"per-batch"` (`AP-BREAKER-SCOPE`, recorded-red); or sits on a phase whose
  `kind` is not one of the three fan-out kinds (`AP-BREAKER-KIND`, recorded-red)
- `base` on any phase but `fanout-redundant`, naming an unknown or non-earlier phase, naming a
  phase that is not `fanout-redundant`, or naming one no earlier `fanout-blind` phase reviewed
  and this phase's own `requires` never reach (`AP-BASE-INVALID`, recorded-red); `base` at all
  under `backend.kind: "workflow"` (`AP-BASE-BACKEND`, recorded-red)
- with `--strict`: any `AP-SIBLING-INVISIBLE` `WARNING` (see below) — never checked on a plain
  compile, which still prints the warning and still writes

**Never infer a missing gating value.** Reject and surface it: a halt that depends on a value the
compiler invented is not a halt.

## Recorded-red validators (issues #77, #74, #75, #79)

A **recorded-red** rule is a validator this plugin added that rejects a spec the compiler at
HEAD `3f62503` would have compiled clean — the whole point of the convention is that the claim
"this used to be silently accepted" is checked, not asserted. `compile_spec.py`'s module-level
`RED_RULES` dict maps each such rule's id to the GitHub issue that motivated it:

```python
RED_RULES = {
    "AP-REFOWNED-NO-PRODUCER": 77,
    "AP-REFOWNED-OUTSIDE-SCOPE": 77,
    "AP-OUTPUT-OUTSIDE-SCOPE": 74,
    "AP-OUTPUT-REFOWNED": 74,
    "AP-CHECK-NOT-RAN": 74,
    "AP-BREAKER-INCOMPLETE": 75,
    "AP-BREAKER-DISABLED": 75,
    "AP-BREAKER-RATIO": 75,
    "AP-BREAKER-SCOPE": 75,
    "AP-BREAKER-KIND": 75,
    "AP-SIBLING-INVISIBLE": 79,
    "AP-BASE-INVALID": 79,
    "AP-BASE-BACKEND": 79,
}
```

`AP-SIBLING-INVISIBLE` is a `WARNING`, not a `REJECTED` line — `test_red_fixtures.py` and
`compile_spec.py --selftest` both treat a `WARNING` exactly like a `REJECTED` line for tagging
and coverage purposes, since both are how this plugin surfaces "something this compiler used to
accept silently no longer passes without comment."

Every `REJECTED`/`WARNING` line a recorded-red validator prints carries its id in brackets, e.g.:

```
REJECTED refereeOwned: [AP-REFOWNED-NO-PRODUCER] declared but no phase of kind
'referee-fixture' produces it; an artifact nothing writes is not protected, it is simply absent
```

Each id in `RED_RULES` has a committed fixture under `scripts/fixtures/red/` that:

1. **compiles clean at HEAD** (`git archive 3f62503 -- plugins/arbeitsplan`, `compile_spec.py
   --spec <fixture>`, exit 0) — it carries the new key (`refereeOwned`) but never the new
   `kind` (`"referee-fixture"`), because HEAD's `KINDS` set already refuses any spec that uses a
   kind it does not know, which would make "HEAD accepted this" false for reasons this feature
   never touched;
2. **is rejected by the current compiler**, citing its rule's id and no unkeyed
   `REJECTED`/`WARNING` line.

`scripts/fixtures/red/MANIFEST.json` lists, per rule, which fixture proves it and the args to
run the compiler with. `scripts/test_red_fixtures.py` is the calibration: it asserts every
`RED_RULES` id has a manifest entry, every entry's rule maps to its declared issue, and (its
optional `--baseline SHA`) that the fixture really did compile clean at that commit rather than
by assumption. `compile_spec.py --selftest` calls it directly, so a red fixture that stopped
going red cannot hide behind a green selftest reported on its own.

## Migrating from `schemaVersion` 1

1. `"backend": "in-session"` → `"backend": {"kind": "in-session", "why": ["writes-shared-tree"], "acknowledgedGaps": []}` — pick the `why` from `references/backend-selection.md`.
2. Every phase gains `mode` (`"auto"` unless it is a planning phase) and `writes` (`worktree` for builders, `none` for referees, `shared` for an in-session landing).
3. Every phase gains `agentType`. A `single-writer` landing phase that had none is `arbeitsplan:synthesizer`.
