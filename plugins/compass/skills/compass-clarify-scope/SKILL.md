---
name: compass-clarify-scope
description: Turns a genuinely underspecified task into a scoped problem statement before solving starts — only when success criteria are actually missing or contradictory, not for requests that are merely broad or open-ended. Use when "done" has no stated definition ("make it better", "clean this up", "fix the issues", "finish the migration" with no criteria given anywhere in the thread), when a request could reasonably be read two structurally different ways with different deliverables, or when compass-solve's own Clarify phase runs at the start of its pipeline. Covers cases where the user themselves flags the gap — "no other details given," "isn't defined anywhere," "there's no definition of what 'done' means" — as well as ones where the ambiguity is only implicit. Do not use for requests with an implicit but genuinely obvious interpretation, or where asking would just be friction — most requests do not need this skill; reserve it for cases where guessing wrong would waste real work.
---

Turn a vague task into a scoped problem statement before any solving,
branching, or drafting starts. Built on two mechanisms from
universal-creator's prompt-engineering technique set, generalized from
their original domains to task-scoping:

- `generate-knowledge.prompt.md`'s generate-facts-before-answering
  step: list what is actually known about the task, numbered, flagging
  any fact under 90% confidence with ⚠️ — generalized from priming a
  science answer to priming a task's scope.
- `active-prompt.prompt.md`'s uncertainty-ranking
  step: score candidate interpretations by confidence, rank ascending,
  and surface the lowest-confidence ones explicitly — generalized from
  selecting few-shot examples to selecting which ambiguities must be
  flagged rather than silently resolved.

Skipping this step means every downstream `compass-*` skill inherits
whatever the first available interpretation happened to be — the
failure mode this skill exists to patch. This is plain skill logic: no
agent file, no Workflow script — everything below runs directly in the
conversation.

## When to use

- The task's phrasing supports more than one reasonable interpretation.
- Success/done criteria aren't stated, or are stated only qualitatively.
- Before `compass-solve`'s Clarify phase, or standalone whenever a task
  needs its scope pinned down before other `compass-*` skills consume it.

Skip this skill when the task is already a well-specified,
single-interpretation instruction with explicit acceptance criteria —
clarifying an already-clear task only adds overhead.

## Step 1 — Generate known facts

List everything actually known about the task: statements made directly
in the request, relevant facts pulled from the codebase/conversation/prior
context, and constraints stated or clearly implied. Number each fact.
Mark any fact below 90% confidence with ⚠️ — mirror generate-knowledge's
exact convention rather than softening it into a prose caveat.

```
known_facts:
1. <fact stated directly in the request>
2. <fact inferred from context, high confidence>
3. <fact inferred from context, low confidence> ⚠️
```

A task with zero known facts beyond the raw request text is itself a
signal — state that plainly rather than padding the list with restated
request text disguised as "facts."

## Step 2 — Score candidate interpretations, rank by uncertainty

For every phrase, term, or requirement in the task that supports more
than one reasonable reading, apply active-prompt's zero-shot
pre-screening step: name the interpretation that would be assumed by
default, and assign it a confidence score 0-100.

| # | Ambiguous element | Default interpretation | Confidence | Other plausible readings |
|---|---|---|---|---|

Sort the table ascending by confidence — the same ranking step
active-prompt uses to select the most informative examples, applied
here to select the most informative ambiguities. Anything scoring below
70 becomes a **flagged uncertainty**: do not silently adopt the default
interpretation for it. Anything at or above 70 may proceed under the
default interpretation, but stays visible in the output — a downstream
skill that later discovers an assumption was wrong needs to see what
was assumed, not just what got flagged.

Apply this same ranking to success criteria specifically: if "done"
isn't stated, or is stated only qualitatively, that is itself a
below-threshold item — flag it rather than inventing a metric and
presenting it as given.

## Step 3 — Produce the scoped problem statement

Emit exactly this structure — it is the contract every other
`compass-*` skill and `compass-solve` reads as their starting point:

```
scoped_task: <one clear restated task with every default interpretation
  from Step 2 stated inline, not left implicit>

known_facts:
  1. <fact> [⚠️ if <90% confidence]
  ...

flagged_uncertainties:
  - element: <ambiguous phrase or requirement>
    default_interpretation: <what will be assumed if not resolved>
    confidence: <0-100, from Step 2>
    other_readings: <alternative interpretations considered>

success_criteria:
  - <criterion> [stated | inferred | missing — needs elicitation before
    compass-draft-revise can score against it]
  ...
```

`scoped_task` must never bury an assumed interpretation in prose — every
default from a below-threshold row in Step 2 is named explicitly, so a
reader (human or another `compass-*` skill) can see exactly what was
assumed and swap it out if it turns out to be wrong.

If a `flagged_uncertainties` entry is load-bearing for the task's
success criteria (the task cannot proceed meaningfully under either
reading without changing the deliverable), surface it to the user
directly and wait for an answer before continuing — do not let a
low-confidence guess about what "done" means propagate silently into
`compass-explore-branches` or `compass-decompose-chain`. Uncertainties
that don't change the deliverable either way may proceed under the
default interpretation, flagged but not blocking.

## Output contract for downstream skills

Contract: `compass-contract-v1` (see `plugin.json`'s `contractVersion` —
bump both together if this table's shape changes incompatibly).

| Field | Shape | Consumed by |
|---|---|---|
| `scoped_task` | string, all defaults stated inline | `compass-explore-branches` (branch-generation input), `compass-decompose-chain` (stage-decomposition input) |
| `known_facts` | numbered list, ⚠️-flagged | any `compass-*` skill needing established context without re-deriving it |
| `flagged_uncertainties` | list of `{element, default_interpretation, confidence, other_readings}` | `compass-solve` (decides whether to pause for user input before Explore) |
| `success_criteria` | list of `{criterion, status}` | `compass-draft-revise` (its own criteria table's starting point) |

Source techniques (vendored locally, no external repo dependency):
`../../references/knowledge/generate-knowledge.md` and
`../../references/knowledge/active-prompt.md` — see `../../references/knowledge/index.md`.

See `../../references/constraints.md` for the context-rot and
plausible-vs-verified guardrails that apply to every `compass-*` skill,
including this one — keep `known_facts` to what's genuinely
load-bearing, not an exhaustive context dump.
