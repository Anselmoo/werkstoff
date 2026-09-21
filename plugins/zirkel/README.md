# zirkel

**Staged reasoning-composition for complex, ambiguous, or multi-faceted tasks.**

A *Zirkel* is the pair of dividers used in *Anreissen* — scribing the layout onto a
workpiece before a single cut is made. It does not remove material; it decides where
the material will be removed, and everything downstream follows the line it scribed.
That is this plugin's job: clarify, explore and decompose are the layout, and
execution follows a line that was drawn deliberately rather than found by cutting.

## Why this exists

Ad hoc prompting for complex or ambiguous tasks tends to skip steps under
pressure — clarification gets rushed, alternatives don't get explored,
self-consistency checks quietly don't happen. zirkel composes the standard
reasoning techniques into one fixed pipeline so a task can't silently skip a
stage, and enforces every guarantee with executable code rather than prose a
model could ignore under load — the difference explained below.

zirkel applies techniques from prompt-engineering theory — clarification,
tree-of-thoughts exploration, chain decomposition, chain-of-thought /
self-consistency / PAL reasoning, RAG-style grounding, ReAct investigation, APE
prompt optimization — as composable skills, unified by a
**Clarify → Explore → Decompose → Execute → Revise** pipeline.

The distinguishing property of this plugin: **its guarantees are enforced by
executable code, not by prose.** Every numeric bound is a named constant, every
"MUST NOT / MUST refuse / MUST pause" rule is a conditional that exits non-zero,
and every persisted artifact is validated on read and write. A skill cannot
quietly skip a rule — the guard's non-zero exit is observable.

## What it is not

- **Not a repository-architecture mapper.** `zirkel-map-relationships`
  traverses relationships whose entities are already established — deriving a
  repo's real import/module graph from source ("map this repo's architecture",
  "show me the real module boundaries", "map stages and wires") belongs to
  `befund-stage-map`, which parses imports per language and writes the
  stage graph other skills consume.
- **Not for simple, well-specified, single-step tasks.** `zirkel-solve` runs
  the full pipeline; it exists for tasks complex or ambiguous enough to need
  staged decomposition, not ones that don't.
- **Not for well-trodden single-step reasoning.** `zirkel-reason-verify`
  climbs its rung ladder only where a concrete failure-mode signal (multi-step
  arithmetic, a costly wrong early assumption, a precision-critical
  calculation, an image/diagram input) makes the extra reasoning worth its
  cost.
- **Not for tuning a one-off prompt.** `zirkel-optimize-instruction` needs
  representative real test cases to score APE candidates against; without them
  it has nothing to optimize toward.

## Install

```
/plugin marketplace add Anselmoo/werkstoff
/plugin install zirkel@werkstoff
```

zirkel ships no PreToolUse hook, so installing it changes nothing by itself —
its guarantees run only when a skill invokes the guard CLI or a workflow
script (see [What is enforced, and what is not](#what-is-enforced-and-what-is-not)).

### Requirements

Python 3, standard library only. Workflow scripts require the Workflow tool;
without it, every skill has a manual path that calls the same Python guards.

### Local development

Point Claude Code at a checkout without registering the marketplace:

```bash
claude --plugin-dir /path/to/werkstoff/plugins/zirkel
```

<!-- rrt:auto:start:example-prompts-intro -->
## Example Prompts

Say any of these to Claude Code once the plugin is installed — they're plain-language
prompts, not exact phrasing Claude has to match. Claude routes them to the skill below
by intent.
<!-- rrt:auto:end:example-prompts-intro -->

##### Run the full pipeline

````prompt
"help me think through this, it's complex and I'm not sure of the right approach"
````

> Triggers `zirkel-solve` — runs the full Clarify → Explore → Decompose → Execute
> → Revise pipeline.

##### Explore before committing

````prompt
"before we commit to an approach, explore a few different ones"
````

> Triggers `zirkel-explore-branches` — proposes and scores multiple viable
> approaches instead of anchoring on the first.

Every `zirkel-explore-branches` run can also persist a self-contained HTML
report — `scripts/build_branch_comparison_html.py` renders the run's
`state.json` as a small-multiples grouped-bar D3 chart, one card per branch,
so the scores never live only in chat history:

![HTML report comparing four branches for how zirkel should persist and surface branch-comparison results — "Inline guard-only summary" (Total 14), "Standalone D3 branch-comparison viewer" (Total 19, highlighted WINNER with an orange border and badge), and "Radar chart for N-axis comparison" (Total 18) — each card showing grouped Feasibility/Impact/Risk bars alongside the branch's description and biggest blocker](assets/branch-comparison-viewer-screenshot.jpg)

That image is reproducible rather than a one-off capture — the run it renders is
committed at `scripts/fixtures/sample_explore_state.json` (four branches whose Totals
are 14 / 19 / 18 / 13, so the winner takes it by a single point over the runner-up and
the report's verdict has to name a blocker rather than a walkover). The builder reads a
staged run at `<repo>/.zirkel/runs/<run-id>/state.json`, which is where the fixture has
to be copied first:

```bash
RUN=9f2b6b1e-1c2b-4c3a-9c3e-2f6a2d6b7a10
mkdir -p "/tmp/zirkel-demo/.zirkel/runs/$RUN"
cp plugins/zirkel/scripts/fixtures/sample_explore_state.json \
   "/tmp/zirkel-demo/.zirkel/runs/$RUN/state.json"
python3 plugins/zirkel/scripts/build_branch_comparison_html.py /tmp/zirkel-demo \
    --run-id "$RUN" \
    --template plugins/zirkel/assets/branch-comparison-viewer.html \
    --d3 plugins/zirkel/assets/inline-d3.html \
    --tokens plugins/zirkel/assets/tokens.css
# -> /tmp/zirkel-demo/.zirkel/runs/<run-id>/branch-comparison.html
```

##### Clarify a fuzzy scope

````prompt
"add caching to the reporting pipeline — the scope is fuzzy, help me pin it down before anything gets built"
````

> Triggers `zirkel-clarify-scope` — surfaces ambiguous phrasing and unstated
> success criteria before any work starts.

##### Break a problem into stages

````prompt
"break this into steps — what depends on what"
````

> Triggers `zirkel-decompose-chain` — splits the problem into a 2-5 stage
> pipeline with explicit input/output contracts per stage, and derives which
> stages can run in parallel from the dependency graph.

##### Score and fix a draft

````prompt
"score this draft against these criteria and fix what's weak"
````

> Triggers `zirkel-draft-revise` — rates 1-5 against each criterion, revises
> only what falls at or below threshold, and reports exactly what changed
> (capped at 2 revision cycles).

##### Ground every claim

````prompt
"don't make this up — ground every claim in the actual code or docs"
````

> Triggers `zirkel-ground-evidence` — requires a file:line, URL, or
> explicitly-flagged prior knowledge behind every factual claim, and refuses
> to assert anything unverified.

##### Investigate step by step

````prompt
"I don't know where the problem is — go find it"
````

> Triggers `zirkel-investigate-dynamically` — runs a Reasoning/Action/Observation
> loop where each observation decides the next step, for cases where the
> sequence of actions can't be planned upfront.

##### Trace a multi-hop chain

````prompt
"trace how A affects D through the whole dependency chain"
````

> Triggers `zirkel-map-relationships` — extracts indexed relationship triples
> and traverses them hop by hop, citing the triple index at every hop.

##### Combine the best of two approaches

````prompt
"the winner's good, but can we fold in what I liked from the runner-up?"
````

> Triggers `zirkel-negotiate-tradeoffs` — synthesizes a hybrid from 2-3
> already-scored branches, but only presents it if it actually beats every
> source branch on at least one axis.

##### Tune a reusable prompt

````prompt
"find the best wording for this system prompt — I have test cases"
````

> Triggers `zirkel-optimize-instruction` — generates one candidate per APE
> framing, scores each against your real test cases, and critiques the winner.
> Needs representative test cases; not for one-off prompts.

##### Guard against a silent reasoning error

````prompt
"walk through this calculation carefully, I can't afford a wrong assumption here"
````

> Triggers `zirkel-reason-verify` — climbs a 4-rung ladder (zero-shot →
> Chain-of-Thought → self-consistency → PAL) matched to the actual
> failure-mode risk, applying Multimodal-CoT first if there's an image or
> diagram involved.

##### Anchor a fuzzy output format

````prompt
"I can't describe the format, but here's an example — make it look like this"
````

> Triggers `zirkel-calibrate-format` — anchors the target shape to 2-5
> concrete input/output examples instead of more prose, enforcing at least
> one near-boundary example so the set actually pins the decision.

##### Write up a finished run

````prompt
"summarize what we just did for the PR"
````

> Triggers `zirkel-summarize-trace` — produces a fixed 7-section record
> (asked, assumed, weighed, run, produced, revised, not done) after a
> `zirkel-solve` pipeline finishes.

##### Check one blocking assumption

````prompt
"before we rely on this, verify it's actually true"
````

> Triggers `zirkel-verify-assumptions` — checks exactly one named assumption
> against real evidence in at most 3 steps; for more than one uncertainty,
> invoke it once per uncertainty.

`zirkel-solve` composes the rest of the pipeline automatically — you rarely need
to name one of the other 13 technique skills directly unless you want just that one
step (see the full table below).

## Components

### Skills (14)

| Skill | Use it when |
|-------|-------------|
| `zirkel-solve` | A task is complex AND ambiguous AND needs staged work — runs the whole pipeline. |
| `zirkel-clarify-scope` | Phrasing is ambiguous, success criteria unstated, scope underspecified. |
| `zirkel-explore-branches` | Multiple viable approaches; anchoring on the first is a risk. |
| `zirkel-decompose-chain` | A problem must become a 2-5 stage pipeline with per-stage contracts. |
| `zirkel-draft-revise` | A draft needs scoring 1-5 against criteria and selective revision. |
| `zirkel-ground-evidence` | Claims must trace to a source; unsupported ones must be refused. |
| `zirkel-investigate-dynamically` | The next action depends on the last result (ReAct loop). |
| `zirkel-map-relationships` | The answer needs multi-hop traversal through indexed triples. |
| `zirkel-negotiate-tradeoffs` | After Explore, synthesize a hybrid of 2-3 branches. |
| `zirkel-optimize-instruction` | Tune the exact wording of a reusable prompt with real test cases (APE). |
| `zirkel-reason-verify` | A concrete failure-mode signal calls for CoT / self-consistency / PAL. |
| `zirkel-calibrate-format` | An output shape is easier to anchor with 2-5 examples than prose. |
| `zirkel-summarize-trace` | Capture a finished `zirkel-solve` run as a fixed 7-section record. |
| `zirkel-verify-assumptions` | Check exactly one named assumption in ≤3 steps. |

### Agents (3)

- **branch-proposer** — proposes one branch under an assigned angle, or scores one
  branch in isolation (used by `zirkel-explore-branches`).
- **instruction-candidate** — drafts / scores / critiques one APE candidate (used
  by `zirkel-optimize-instruction`).
- **reasoning-path** — one isolated reasoning attempt under one strategy (used by
  `zirkel-reason-verify`'s self-consistency tier).

## What is enforced, and what is not

zirkel registers no PreToolUse hook — nothing here is a denial at the tool-call
layer. Instead, every skill invokes a guard at each decision point, and the
guard's non-zero exit is what makes a rule observable rather than aspirational.

### Enforcement layer

- `scripts/zirkel_lib.py` — the guard library: all numeric bounds as named
  constants, all rules as functions that raise `GuardError`.
- `scripts/zirkel.py` — the CLI every skill invokes (`python3
  ${CLAUDE_PLUGIN_ROOT}/scripts/zirkel.py <check> -`). Exit 0 = pass, exit 2 =
  rule violated, exit 3 = usage error.
- `scripts/test_zirkel.py` — 53 assertions proving each guard both accepts valid
  input and refuses invalid input. Run: `python3 scripts/test_zirkel.py`.
- `workflows/*.js` — parallel orchestration for the fan-out skills
  (`solve`, `explore-branches`, `reason-verify`, `optimize-instruction`), each
  embedding the same bounds as JS constants with `throw` guards.

### How enforcement works

Skills call the guard CLI at each decision point. For example, `zirkel-decompose-chain`
does not merely *tell* the model to keep 2-5 acyclic stages — it runs:

```bash
echo '{"stages":[...]}' | python3 ${CLAUDE_PLUGIN_ROOT}/scripts/zirkel.py decompose -
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

## Settings

`.claude/zirkel.local.md` — copy it into your project and set `max_branch_count`
in its frontmatter to lower the Explore ceiling. The effective cap is always
**min(6, max_branch_count)**.

## The report

Every `zirkel-explore-branches` run can persist a self-contained HTML report
comparing branch scores — see the screenshot and build command under
[Explore before committing](#explore-before-committing) in Example Prompts
above.

## Design decisions

*(spec was silent here)*

Where the spec was silent, these choices were made and are noted here:

1. **Enforcement lives in a Python guard CLI (`scripts/zirkel.py`) plus JS
   workflow guards.** Python is invokable directly via Bash from any skill without
   the Workflow tool, so the guarantees hold even when workflows aren't available.
   The four fan-out skills also ship `workflows/*.js` that re-encode the same
   constants — belt and suspenders.
2. **Risk is never inverted, anywhere.** The spec mandates Total = F + I + R with
   Risk not inverted, and highest total wins. For internal consistency, zirkel
   treats "outperform on an axis" (in `zirkel-negotiate-tradeoffs`) as *a strictly
   higher number on that axis* for all three axes, Risk included. This is the only
   convention that keeps selection and hybrid-comparison coherent.
3. **Persisted state lives under `.zirkel/`** (git-ignored). The state artifact's
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

## Verifying a change to this plugin

```bash
python3 plugins/nacharbeit/scripts/nacharbeit_lint.py plugins/zirkel --docs-root docs
python3 plugins/zirkel/scripts/test_zirkel.py                     # -> "53 passed, 0 failed"
python3 plugins/zirkel/scripts/test_build_branch_comparison_html.py
bash scripts/ci/check-js-syntax.sh                                  # workflows/*.js shape
```

## License

MIT
