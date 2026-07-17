---
name: compass-verify-assumptions
description: This skill should be used when exactly one specific, named assumption or flagged uncertainty needs to be checked against real evidence in a bounded number of steps — typically a compass-clarify-scope flagged_uncertainties entry that compass-solve would otherwise have to pause the whole pipeline on, or a downstream stage that needs one upstream assumption confirmed before it can proceed. Use when you already know exactly which assumption to check. Not for open-ended discovery with no fixed target (that is compass-investigate-dynamically's job) — this skill is bounded to at most 3 tool calls and a single named element, never a general research pass.
---

Resolve one flagged uncertainty with the minimum evidence needed to
either confirm it, refute it in favor of an alternative reading, or
conclude honestly that it can't be resolved with what's available —
never more than 3 tool calls, and never for more than one assumption at
a time. Combines two mechanisms from this plugin's own technique set:

- `compass-investigate-dynamically`'s Reasoning/Action/Observation loop
  shape (`../../references/knowledge/react.md`,
  `../../references/knowledge/art.md`) — but hard-capped at 3 iterations
  here, where that skill has no fixed limit. This skill exists
  specifically for "verify this one thing fast," not open-ended
  discovery.
- `compass-ground-evidence`'s citation-or-refuse discipline
  (`../../references/knowledge/rag.md`) — every resolution must cite
  `file:line` or a URL; if no source settles it within the step budget,
  use the exact same refusal pattern rather than a soft hedge.

See `../../references/constraints.md` for the context-rot and
plausible-vs-verified constraints that apply across every `compass-*`
skill.

**Non-goal:** this does not replace `compass-investigate-dynamically` for
open-ended discovery — use that skill when you don't know what you'll
find or how many steps it will take. Use this skill only when you have a
specific, already-named assumption to test and a tight step budget.

## Step 0 — Confirm the input

This skill needs exactly one uncertainty entry in
`compass-clarify-scope`'s own shape (see
`../../references/pipeline-cheatsheet.md`'s Clarify-output section for
the full contract):

```
{
  element: string,                 // the ambiguous phrase or requirement
  default_interpretation: string,  // what would be assumed if unresolved
  confidence: number,              // 0-100, from compass-clarify-scope Step 2
  other_readings: string,          // alternative interpretations considered
  blocking: boolean                // (optional here) whether the pipeline is paused on this entry
}
```

If handed more than one entry, process them independently — one full
Step 1-3 loop (and one 3-call budget) per entry, never a shared budget
across entries.

## Step 1-3 — Bounded Reasoning / Action / Observation loop (max 3 steps)

Run the same loop shape `compass-investigate-dynamically` uses, in the
same explicit format:

```
Step N (of at most 3)
Reasoning: <what would settle this specific element, and why this action checks it>
Action: <Read/Grep/Glob/WebFetch/WebSearch>(<arguments>)
Observation: <what the action actually returned>
```

Each Reasoning line must name specifically what would raise `confidence`
above 90, confirm an `other_readings` alternative instead, or establish
that no available source settles it — not a generic "let me look into
this." Stop as soon as one of Step 4's three outcomes is reached, even
if fewer than 3 steps were used — do not spend a step you don't need
just because the budget allows it.

If Step 3 completes with no outcome reached, stop anyway — the budget is
hard, not a target to exhaust before giving up.

## Step 4 — Report exactly one outcome

Report exactly one of:

1. **Resolved (confidence raised)** — new `confidence` (must exceed 90),
   citing the source(s) from the Observations above (`file:line` or
   URL) per `compass-ground-evidence`'s citation discipline. State the
   confirmed `default_interpretation` (unchanged, now verified).
2. **Resolved (reading changed)** — evidence supported one of
   `other_readings` instead of the original `default_interpretation`.
   Report the new `default_interpretation`, the confidence in it, and
   cite the source(s) that support the change.
3. **`still_unresolved: true`** — use `compass-ground-evidence`'s exact
   RAG refusal template, filled in for this element: "The available
   [sources actually searched] do not contain sufficient information to
   resolve [the element]." Report which sources were checked (even
   though they didn't settle it) so a later pass doesn't repeat the same
   3 steps.

Never report a fourth outcome (e.g. "probably resolved" or "leaning
toward") — every resolution is exactly one of these three, or the loop
ran out of budget and outcome 3 applies.

## Standalone use vs. inside `compass-solve`

Invocable directly on any single flagged uncertainty. Inside
`compass-solve`'s pipeline: offered at Step 1 for each
`blockingUncertainties` entry before pausing for the user (if this skill
resolves it, the user doesn't need to be asked about that entry), and
available to a Step 4 (Execute) stage's own dispatch when that stage's
output contract depends on an upstream assumption it needs settled
before proceeding.
