# `workflow.json` — the compiled workflow spec

This is the **coded handoff**. Every later phase reads it; nothing in arbeitsplan re-derives its
contents from prose.

## Why this file is a schema and not a description

**Contents** — [why a schema](#why-this-file-is-a-schema-and-not-a-description) · [location](#location) · [schema](#schema) · [worked instance](#worked-instance) · [rejections](#rejections-at-compile-time)

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
| `schemaVersion` | `"1"` | yes | bumped only on a breaking change; a reader that does not recognise it **refuses**, never guesses |
| `runId` | string | yes | `ap-<YYYY-MM-DD>-<4 hex>`. Also the takt marker namespace. Charset: `[A-Za-z0-9._-]+`, no `/`, no `..` |
| `problem` | object | yes | see below |
| `writeScope` | string[] | yes | fnmatch globs. **Never empty** — an empty scope is rejected at compile, not treated as "anything" |
| `budget` | object | yes | `totalDispatches` (int > 0), `wallClockMinutes` (int > 0) |
| `phases` | object[] | yes | 1..8 phases, see below |
| `delegates` | object[] | no | optional cross-plugin beats (compass et al.) |
| `backend` | `"in-session"` \| `"matrix"` | yes | which execution backend the run uses |

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
| `kind` | `"fanout-redundant"` \| `"fanout-blind"` \| `"single-writer"` | determines who may hold Write |
| `pattern` | string | an id from `references/patterns.md`. Unknown id ⇒ **reject**, never improvise |
| `fanOut` | int | 1..16. Required for both `fanout-*` kinds |
| `modelTier` | `"haiku"` \| `"sonnet"` \| `"opus"` | **always explicit** — an omitted tier inherits the session's model and silently defeats tiering (`docs/orchestration/references/delegation.md`) |
| `agentType` | string | namespaced, e.g. `arbeitsplan:candidate-builder` |
| `angles` | string[] | one per candidate for `fanout-redundant`; `length` must equal `fanOut`. This is how widening is expressed |
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
  "schemaVersion": "1",
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
      "requires": ["refereed"],
      "marker": "landed"
    }
  ],
  "delegates": [
    { "plugin": "compass", "skill": "compass-explore-branches", "beat": "branches-explored", "optional": true }
  ],
  "backend": "in-session"
}
```

## Rejections at compile time

A spec is **not written** if any of these hold. Each is a refusal with the offending key named, never
a default silently supplied:

- `problem.shape == "question"` — emit `out-of-scope-reasoning`, point at `compass:compass-solve`
- `writeScope` empty or absent
- no acceptance criterion carries a runnable `check`
- a `phases[].pattern` not present in `references/patterns.md`
- `angles.length != fanOut` on a `fanout-redundant` phase
- `modelTier` absent on any phase
- `requires` naming a marker no earlier phase creates (a dangling dependency)
- a marker created by two phases
- `budget.totalDispatches` less than the sum of every phase's `fanOut`

**Never infer a missing gating value.** Reject and surface it: a halt that depends on a value the
compiler invented is not a halt.
