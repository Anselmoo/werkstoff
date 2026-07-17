# Compass decision triage tables

One decision table per gate in the `compass-solve` pipeline. Each
`compass-*` skill's own `SKILL.md` remains the authoritative prose
description of its skip criteria — these tables are a fast-scan summary
for deciding whether a gate applies, not a replacement for reading the
skill itself before invoking it.

## Clarify gate

Source: `compass-clarify-scope/SKILL.md` ("When to use" / "Skip this
skill when", lines 27-36).

| Gate | Question | If yes | If no | Signal to look for |
|---|---|---|---|---|
| Clarify | Is success undefined, or does the task support more than one structurally different reading? | Run `compass-clarify-scope` | Proceed directly with the task as stated | No stated "done" criteria anywhere in the thread; a phrase/requirement that supports two genuinely different deliverables; the user themselves flags the gap ("no other details given", "isn't defined anywhere") |

## Explore gate

Source: `compass-solve/SKILL.md` Step 2 (lines 92-102).

| Gate | Question | If yes | If no | Signal to look for |
|---|---|---|---|---|
| Explore | Does the scoped task have multiple genuinely viable approaches worth weighing before committing? | Invoke `compass-explore-branches` with `scopedProblem: scopedTask`; feed the winning branch's `description` to Decompose as `selectedApproach` | Skip straight to Decompose with `scopedTask` — `selectedApproach` stays unset | A real strategic fork (build vs. buy, sequential vs. parallel, minimal vs. ambitious) rather than one obvious approach; a narrow bug fix or single well-defined deliverable is a "no" |

## Execute-mode gate

Source: `solve-orchestrate.js`'s `MODE_SKILLS_ALL` / `OPTIONAL_MODE_SKILLS_ALL`
(lines 328-337). This decision is made per-stage, at the start of that
stage's own dispatch, never hardcoded upfront.

| Gate | Question | If yes | If no | Signal to look for |
|---|---|---|---|---|
| Execute mode | Does this stage's content need `compass-reason-verify`? | Apply that methodology within the stage's own dispatch | — | Multi-step/dependent calculation, a single-answer puzzle where an early wrong assumption is costly, precision-critical arithmetic, or image/diagram input |
| Execute mode | Does this stage's action/tool sequence need to be discovered turn by turn? | Apply `compass-investigate-dynamically` as your own Reasoning/Action/Observation loop within this dispatch | — | The next action genuinely can't be planned before seeing the previous action's result |
| Execute mode | Does this stage's deliverable make factual claims needing citation? | Apply `compass-ground-evidence` | — | The output asserts facts that could be wrong, or must refuse to assert beyond what's verified |
| Execute mode | Is this stage's output format/style/schema ambiguous or non-standard? | Apply `compass-calibrate-format` | — | No obvious default shape for the deliverable |
| Execute mode (optional) | Does this stage involve entity/dependency/causal-graph traversal? | Apply `compass-map-relationships` | — | Org structures, dependency graphs, causal chains |
| Execute mode (optional) | Is this stage's deliverable itself a reusable instruction/prompt for a recurring task, with test cases available? | Apply `compass-optimize-instruction` | — | Not a general prompt-linting request — must have (or be able to elicit) representative test cases |
| Execute mode | None of the above apply | — | Fulfill the output contract with ordinary reasoning, report `modesUsed: []` | The stage is simple enough that forcing a methodology onto it would be the anchoring-on-process failure mode this plugin warns against |
