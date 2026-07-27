# compass

**Staged reasoning-composition for complex, ambiguous, or multi-faceted tasks.**

compass applies techniques from prompt-engineering theory — clarification,
tree-of-thoughts exploration, chain decomposition, chain-of-thought /
self-consistency / PAL reasoning, RAG-style grounding, ReAct investigation, APE
prompt optimization — as composable skills, unified by a
**Clarify → Explore → Decompose → Execute → Revise** pipeline.

The distinguishing property of this plugin: **its guarantees are enforced by
executable code, not by prose.** Every numeric bound is a named constant, every
"MUST NOT / MUST refuse / MUST pause" rule is a conditional that exits non-zero,
and every persisted artifact is validated on read and write. A skill cannot
quietly skip a rule — the guard's non-zero exit is observable.

## Components

### Skills (14)

| Skill | Use it when |
|-------|-------------|
| `compass-solve` | A task is complex AND ambiguous AND needs staged work — runs the whole pipeline. |
| `compass-clarify-scope` | Phrasing is ambiguous, success criteria unstated, scope underspecified. |
| `compass-explore-branches` | Multiple viable approaches; anchoring on the first is a risk. |
| `compass-decompose-chain` | A problem must become a 2-5 stage pipeline with per-stage contracts. |
| `compass-draft-revise` | A draft needs scoring 1-5 against criteria and selective revision. |
| `compass-ground-evidence` | Claims must trace to a source; unsupported ones must be refused. |
| `compass-investigate-dynamically` | The next action depends on the last result (ReAct loop). |
| `compass-map-relationships` | The answer needs multi-hop traversal through indexed triples. |
| `compass-negotiate-tradeoffs` | After Explore, synthesize a hybrid of 2-3 branches. |
| `compass-optimize-instruction` | Tune the exact wording of a reusable prompt with real test cases (APE). |
| `compass-reason-verify` | A concrete failure-mode signal calls for CoT / self-consistency / PAL. |
| `compass-calibrate-format` | An output shape is easier to anchor with 2-5 examples than prose. |
| `compass-summarize-trace` | Capture a finished `compass-solve` run as a fixed 7-section record. |
| `compass-verify-assumptions` | Check exactly one named assumption in ≤3 steps. |

### Agents (3)

- **branch-proposer** — proposes one branch under an assigned angle, or scores one
  branch in isolation (used by `compass-explore-branches`).
- **instruction-candidate** — drafts / scores / critiques one APE candidate (used
  by `compass-optimize-instruction`).
- **reasoning-path** — one isolated reasoning attempt under one strategy (used by
  `compass-reason-verify`'s self-consistency tier).

### Enforcement layer

- `scripts/compass_lib.py` — the guard library: all numeric bounds as named
  constants, all rules as functions that raise `GuardError`.
- `scripts/compass.py` — the CLI every skill invokes (`python3
  ${CLAUDE_PLUGIN_ROOT}/scripts/compass.py <check> -`). Exit 0 = pass, exit 2 =
  rule violated, exit 3 = usage error.
- `scripts/test_compass.py` — 46 assertions proving each guard both accepts valid
  input and refuses invalid input. Run: `python3 scripts/test_compass.py`.
- `workflows/*.js` — parallel orchestration for the fan-out skills
  (`solve`, `explore-branches`, `reason-verify`, `optimize-instruction`), each
  embedding the same bounds as JS constants with `throw` guards.

## How enforcement works

Skills call the guard CLI at each decision point. For example, `compass-decompose-chain`
does not merely *tell* the model to keep 2-5 acyclic stages — it runs:

```bash
echo '{"stages":[...]}' | python3 ${CLAUDE_PLUGIN_ROOT}/scripts/compass.py decompose -
```

which validates stage count, entry point, dangling references, and cycles (via
Kahn's algorithm), returns the topological waves, and **exits non-zero** if the
graph is invalid. The model must fix the plan before proceeding — the rule is
mechanically enforced.

Rules enforced in code (non-exhaustive):

- Clarify: confidence < 70 → flagged; known fact < 90 → ⚠️; blocking uncertainty →
  `must_pause`.
- Decompose: 2 ≤ stages ≤ 5; ≥1 entry point; no dangling deps; acyclic.
- Explore: default 3 branches; cap = min(6, config); Total = raw sum (Risk not
  inverted); highest-total wins, ties → lower risk.
- Draft-revise: 1-5 scale; default threshold 3; revise only ≤ threshold; changes
  list required; ≤ 2 cycles.
- Reason-verify: rung gates; Rung 2a = exactly 3 strategies; multimodal-CoT
  precedence.
- Verify-assumptions: ≤ 3 steps; one assumption per invocation; confidence gate 90.
- Ground-evidence: inline citation per claim; exact RAG refusal template.
- Map: ≤ ~50 triples; every hop cites a real triple index.
- Optimize: exactly 5 framings; tie-break by framing precedence.
- Negotiate: precondition winner-selected; hybrid must outperform every source on
  ≥1 axis.
- Summarize-trace: exactly 7 sections; omit "Approaches weighed" iff no Explore;
  "What was revised" always present; every dag stage listed.
- Solve: phase order; blocking pause; topological waves; runtime mode dispatch.
- Write scope: path traversal, absolute paths, and out-of-dir targets rejected
  *before* any write.

## Installation & testing

```bash
# Try locally
cc --plugin-dir /path/to/compass

# Run the enforcement test suite
python3 scripts/test_compass.py    # -> "46 passed, 0 failed"
```

Requires Python 3 (standard library only). Workflow scripts require the Workflow
tool; without it, every skill has a manual path that calls the same Python guards.

## Configuration

Copy `.claude/compass.local.md` into your project and set `max_branch_count` in its
frontmatter to lower the Explore ceiling. The effective cap is always
**min(6, max_branch_count)**.

## Design decisions

Where the spec was silent, these choices were made and are noted here:

1. **Enforcement lives in a Python guard CLI (`scripts/compass.py`) plus JS
   workflow guards.** Python is invokable directly via Bash from any skill without
   the Workflow tool, so the guarantees hold even when workflows aren't available.
   The four fan-out skills also ship `workflows/*.js` that re-encode the same
   constants — belt and suspenders.
2. **Risk is never inverted, anywhere.** The spec mandates Total = F + I + R with
   Risk not inverted, and highest total wins. For internal consistency, compass
   treats "outperform on an axis" (in `compass-negotiate-tradeoffs`) as *a strictly
   higher number on that axis* for all three axes, Risk included. This is the only
   convention that keeps selection and hybrid-comparison coherent.
3. **Persisted state lives under `.compass/`** (git-ignored). The state artifact's
   gating fields (`run_id`, `raw_task`, `phase`, `explore_ran`) are mandatory and
   validated on both read and write; a record missing one is rejected, never
   defaulted or repaired. Writes go only through `state-write`, which enforces
   write scope before touching disk.
4. **`blocking` is a required first-class field on every uncertainty**, not
   inferred from confidence. Confidence < 70 forces *flagging*; `blocking: true`
   forces the *pipeline pause*. They are independent gates, so both are explicit.
5. **Six proposer angles** (conservative, ambitious, pragmatic, contrarian,
   minimal, maximal) back the branch cap of 6, so a maxed-out Explore still has a
   distinct angle per branch.
6. **Second revision cycle is the hard ceiling** (`DRAFT_MAX_REVISION_CYCLES = 2`):
   the first pass plus one escalation. If criteria still fail after two cycles, the
   skill reports the residual rather than looping.
7. **Execution mode is a first-class key** (`mode` + `mode_decided_at: "runtime"`),
   validated by `stage-dispatch`, so "decide the mode at runtime" is checkable
   rather than aspirational.

## License

MIT
