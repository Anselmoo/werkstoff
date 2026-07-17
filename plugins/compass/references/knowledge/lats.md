---
type: prompting-technique
title: LATS (Language Agent Tree Search)
description: ReAct-style reasoning per node combined with tree search — branch, score, and backtrack from low-scoring branches — a harder-problem escalation tier over a single linear trace.
resource: ../examples/lats.prompt.md
tags: [compass-investigate-dynamically]
timestamp: 2026-07-16T00:00:00Z
---

# LATS — Language Agent Tree Search

For investigations where a single linear ReAct/ART trace isn't reliable
enough — multiple candidate action sequences need exploring and scoring,
with the option to abandon a low-scoring branch and try another: combine
ReAct-style Reasoning/Action/Observation at each node with tree search
(branch to multiple candidate next-actions, score intermediate states,
backtrack from weak branches).

## Mechanism

At each node: Reasoning/Action/Observation as in ReAct, but instead of
committing to one action, branch to several candidates, self-evaluate
each resulting state, and expand only the strongest — backtracking to a
prior node when a branch's score drops below its siblings, rather than
continuing to sink effort into it.

## When to apply

- A single linear investigation trace has already proven unreliable, or
  the task has genuinely distinct candidate strategies worth comparing
  before committing
- The added cost of branching/scoring/backtracking is worth it — for a
  short, low-ambiguity lookup, plain ReAct is cheaper

## Examples

### In `../examples/lats.prompt.md`

A research task where the first branch's evaluation score is low,
triggering a backtrack to try a second candidate action before
continuing.

### In werkstoff

**`compass-explore-branches`/`explore-branches-scan.js` is a partial
analog, not full LATS**: it already does the Propose (branch to
distinct candidate approaches) and Score (Feasibility/Impact/Risk,
ReAct-adjacent self-evaluation of each candidate) halves of LATS's
mechanism — but the workflow runs exactly one flat round (Propose →
Score → deterministic Select) with **no backtracking or iterative
multi-level re-expansion**, unlike LATS's actual tree search. Stated
honestly here rather than claimed as a full match:
`compass-investigate-dynamically` documents LATS as the harder-problem
escalation tier this repo's tooling only partially implements today.
