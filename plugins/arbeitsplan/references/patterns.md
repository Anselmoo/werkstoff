# The pattern catalog

The frozen set of agentic patterns `arbeitsplan-compile` may put in a `workflow.json`, each with the
configuration that has actually been measured rather than assumed.

**A `phases[].pattern` value not in this file is rejected at compile time.** The compiler never
improvises a pattern, and `arbeitsplan-patterns` may only *add* candidates to a proposal — each
carrying a citation — never silently override a measured entry below.

**Contents** — [machine-readable index](#machine-readable-index) · [accepted patterns](#accepted-patterns) · [rejected patterns](#rejected-patterns-named-so-the-compiler-can-refuse-them-by-name)

The accepted set is `best-of-n`, `blind-referee`, `escalating-batch`, `per-batch-breaker`,
`select-then-synthesize`, `self-consistency-vote`, `tribunal`, `map-reduce-disjoint`,
`calibrate-then-measure`, `ablation-matrix`. The rejected set is `serial-fix-loop`,
`partition-then-merge-worktrees`, `build-and-verify-in-one-dispatch`, `cumulative-breaker`,
`unmeasured-counts-as-failure` — each with the measurement that rejected it.

## How to read the evidence column

`measured-here` means this repository ran it and wrote the number down; the citation is the file.
`measured-elsewhere` means a cited external source. `reasoned` means neither — it is a defensible
default with no number behind it, and it says so. A `reasoned` entry is not forbidden; pretending it
is `measured` is.

## Machine-readable index

A parser must not have to infer acceptance from a markdown heading. This block is the authority;
the prose below is the rationale. `compile_spec.py` reads **this**, and fails loudly if a `### ` id
in the body is absent from it (a pattern documented but not indexed is invisible to the compiler,
which is the silent-failure shape this repository keeps getting burned by).

```json
{
  "accepted": [
    "best-of-n", "blind-referee", "escalating-batch", "per-batch-breaker",
    "select-then-synthesize", "self-consistency-vote", "tribunal",
    "map-reduce-disjoint", "calibrate-then-measure", "ablation-matrix"
  ],
  "rejected": [
    "serial-fix-loop", "partition-then-merge-worktrees",
    "build-and-verify-in-one-dispatch", "cumulative-breaker",
    "unmeasured-counts-as-failure"
  ],
  "delegated": {
    "self-consistency-vote": "compass:compass-reason-verify",
    "tribunal": "andon:andon-verify"
  }
}
```

---

## Accepted patterns

### `best-of-n` — redundant candidates, one lands

| | |
|---|---|
| **applies when** | one scope, several plausible implementations, and you can state acceptance criteria |
| **fan-out** | 3 (default). 2 gives no tie-break; above 5 the marginal candidate rarely wins |
| **model tier** | `sonnet`. Raise to `opus` only when the acceptance criteria need design judgement |
| **stop rule** | one pass. Never re-dispatch a losing angle — widen with a *new* angle instead |
| **cost** | `fanOut` dispatches + `fanOut` referee dispatches |
| **evidence** | `measured-here` — `compass-explore-branches` establishes the isolation requirement: "Generate branches independently and in parallel, score each in isolation … Parallel independence is what prevents anchoring — it is **structural**, not a suggestion" |

Each candidate gets a distinct **angle**, and `angles.length == fanOut` is enforced. Angles are how
this pattern widens; identical prompts N times measure sampling noise, not approaches.

### `blind-referee` — judge the artifact, never the argument

| | |
|---|---|
| **applies when** | a candidate must be checked against a contract and the builder's own case would bias it |
| **fan-out** | one dispatch per candidate, never batched |
| **model tier** | `sonnet` |
| **stop rule** | one pass; verdicts are an **allowlist** |
| **cost** | one dispatch per candidate |
| **evidence** | `measured-here` — `plugins/matrize/agents/decode-referee.md:18-20`, repeated in three places: *an agent asked "is this right?" while holding the case for it will agree; one asked "what does this source say?" will not* |

Non-negotiables: the referee receives the acceptance criteria and the **diff only** — never the
builder's rationale, confidence, or summary; if a dispatch leaks the rationale the referee must
ignore it **and report that it was present**. One candidate per dispatch, and one candidate's verdict
is never inferred from another's.

Verdicts: `accepted`, `accepted_different_approach`, `rejected`, `cannot_judge`. Only `accepted`
lands — an allowlist, because matrize's prior denylist admitted
`reproduced_different_relation` and thereby fed a token an invalid relation under a confirmed card
(`decode.js:207-218`). `rejected` and `cannot_judge` are **never collapsed**: one says the candidate
is wrong, the other says nothing is known.

### `escalating-batch` — widen the fan-out, keep the breaker sharp

| | |
|---|---|
| **applies when** | more work items than one batch should carry |
| **fan-out** | 4 → 8 → 16, cap 16 |
| **model tier** | inherit the phase's |
| **stop rule** | per-batch breaker, below |
| **cost** | linear in items |
| **evidence** | `measured-here` — `plugins/matrize/workflows/decode.js:64-68` — "Beyond the runtime's own concurrency cap a bigger batch buys no speed and only coarsens the breaker" |

### `per-batch-breaker` — the anti-loop primitive

| | |
|---|---|
| **applies when** | any fan-out phase |
| **threshold** | trip when `accepted * 3 < measured * 2` (strictly below 2/3) |
| **scope** | **per batch, never cumulative** |
| **denominator** | excludes the unmeasured class entirely |
| **on trip** | abort and surface. **Never re-dispatch** |
| **evidence** | `measured-here` — `decode.js:158-161`: "a cumulative rate lets healthy early batches mask a batch that has started failing, and fires one full (expensive) batch too late" |

Two distinct aborts, never conflated:

- `measured == 0` → **acquisition problem**. Nothing was measured; the infrastructure failed. Fix the
  environment, not the contract.
- `accepted * 3 < measured * 2` → **contract problem**. Report, verbatim from `decode.js:172`'s
  shape: *"The correct response is a better contract, not more agents."*

### `select-then-synthesize` — the gated hybrid

| | |
|---|---|
| **applies when** | the winner is good and a runner-up has one element worth taking |
| **fan-out** | exactly 1 writer |
| **model tier** | `sonnet` |
| **stop rule** | the hybrid must beat the plain winner on **≥1 declared acceptance criterion**, or the plain winner lands unchanged |
| **cost** | 1 dispatch, only when opted into |
| **evidence** | `measured-here` — `compass-negotiate-tradeoffs`' guard "refuses (non-zero exit) unless the hybrid outperforms EVERY source on at least one axis" |

One writer, so still zero merge conflict. The borrowed elements are **named explicitly** in the
dispatch; "take the good bits" is not a specification.

### `self-consistency-vote` — three isolated attempts, majority

| | |
|---|---|
| **applies when** | a single correct answer exists and the question is reasoning, not construction |
| **fan-out** | exactly 3, one per strategy |
| **model tier** | `sonnet` |
| **stop rule** | majority; report agreement as `N/3` |
| **cost** | 3 dispatches |
| **evidence** | `measured-here` — `compass-reason-verify` Rung 2a |

**Delegate to `compass:compass-reason-verify` when compass is installed.** arbeitsplan does not
reimplement it.

### `tribunal` — defender, challenger, adjudicator

| | |
|---|---|
| **applies when** | a claim of "this is done/proven" needs adversarial testing |
| **fan-out** | 2 blind advocates in parallel, then 1 adjudicator |
| **model tier** | `sonnet` advocates, `opus` adjudicator |
| **stop rule** | one pass; a Tier-1 structural contradiction is non-overridable |
| **cost** | 3–4 dispatches |
| **evidence** | `measured-here` — `andon-verify` strategy (a) |

**Delegate to `andon:andon-verify` when andon is installed.**

### `map-reduce-disjoint` — partitioned fan-out

| | |
|---|---|
| **applies when** | work splits into provably non-overlapping write scopes |
| **fan-out** | one per partition, cap 16 |
| **model tier** | `haiku` for mechanical partitions, `sonnet` otherwise |
| **stop rule** | one pass |
| **cost** | linear |
| **evidence** | `measured-elsewhere` — `superpowers:dispatching-parallel-agents` |

**Admissible only with a computed disjointness proof.** `scope-prover` derives each partition's write
set from the declared `writeScope`; a partition with no declared scope is **rejected, never assumed
disjoint**. `delegation.md` is explicit that "Independence is a precondition the controller
establishes before dispatching, not something the runtime discovers or enforces."

### `calibrate-then-measure` — verify the instrument first

| | |
|---|---|
| **applies when** | a finder, grader or guard will decide something expensive |
| **fan-out** | n/a |
| **stop rule** | if the instrument misses planted defects, fix the instrument — the run does not proceed |
| **cost** | one calibration pass |
| **evidence** | `measured-here` — `nacharbeit-review` calibrates against planted fixtures and a sealed hold-out before finding anything |

### `ablation-matrix` — fresh processes, present/absent arms

| | |
|---|---|
| **applies when** | independence must be total, or a plugin's own contribution must be isolated |
| **fan-out** | `cases × models × plugin_states × repeats` |
| **model tier** | per cell, via `--model` — inheritance is structurally impossible |
| **stop rule** | one sweep; disagreement across `repeats` is `UNSTABLE`, not a retry trigger |
| **cost** | one `claude -p` process per cell; runs **outside** the session |
| **evidence** | `measured-here` — `test/plugins/run.sh`; `measured-elsewhere` — `quo-warranto/tools/run_matrix.py` |

See `references/matrix-schema.md`. The skill compiles and hands over; it never executes.

---

## Rejected patterns — named so the compiler can refuse them by name

### `serial-fix-loop` — REJECTED

Retry the same scope with the same agent until a reviewer passes it.

**Why rejected:** `superpowers:subagent-driven-development/SKILL.md:372-429` runs up to 5 rounds ×
(1 fix + 1 re-review) per task, and concedes the outcome at `:495` — *"Past the cap, rounds don't
converge — the failure is structural."* Up to 10 dispatches per task to reach an admission the shape
of the failure already predicted.

**Instead:** widen. New independent candidates under new angles. arbeitsplan's hook denies a repeat
`(phase, scope, promptHash)` outright.

### `partition-then-merge-worktrees` — REJECTED

N worktrees each doing *different* work, reconciled by git merge at the end.

**Why rejected:** `subagent-driven-development/SKILL.md:282` forbids parallel implementers *inside* a
worktree explicitly "(conflicts)", which forces parallelism up to the worktree level, where the
conflicts reappear at integration and cost more.

**Instead:** `best-of-n`. N worktrees doing the *same* work, N−1 deleted. Integration cost is zero
because nothing is ever merged.

### `build-and-verify-in-one-dispatch` — REJECTED

**Why rejected:** `docs/orchestration/references/delegation.md:148-165` — "Building and verifying in
the same dispatch collapses a check that exists specifically to catch what a generous self-review
misses."

**Instead:** `blind-referee`.

### `cumulative-breaker` — REJECTED

Track acceptance across all batches and trip on the running total.

**Why rejected:** `decode.js:158-161` — healthy early batches mask a batch that has started failing,
and the breaker fires one full expensive batch too late.

**Instead:** `per-batch-breaker`.

### `unmeasured-counts-as-failure` — REJECTED

Treat a candidate that could not be built, run, or judged as a rejection.

**Why rejected:** it makes the breaker measure the weather instead of the work — an infrastructure
outage trips the contract alarm and, in any design with a retry, feeds the loop. This repository has
derived the counter-rule three separate times: `test/plugins/run.sh`'s `ERROR` ("a case whose error
count is above zero has no rate, only missing data"), `decode.js:44-46`'s `readable: false` excluded
from the denominator, and `quo-warranto/scripts/run_trigger_evals.py`'s `INDETERMINATE` ("not FAIL,
because the case was never fairly measured").

**Instead:** the unmeasured class is excluded from the denominator, always, everywhere.
