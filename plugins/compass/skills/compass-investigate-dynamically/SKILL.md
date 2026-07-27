---
name: compass-investigate-dynamically
description: >-
  Works a problem whose next action can only be chosen after seeing the last
  result — a Reasoning / Action / Observation loop where each observation
  determines the next step. Use when the sequence of tool calls cannot be planned
  upfront: "figure out why X is happening", "trace this through the system", "I
  don't know where the problem is, go find it", open-ended debugging or discovery,
  or an Execute stage of compass-solve whose steps are unknown at the start.
---

# compass-investigate-dynamically

Run an explicit **Reasoning / Action / Observation** loop. Each step's action is
chosen from what the previous observation revealed — not from a plan made upfront.

## The loop

For each step, write three labeled parts:

- **Reasoning** — name the specific remaining unknown you are trying to close.
- **Action** — the single tool call that closes *that named gap*. **Choose a tool
  only when your Reasoning names a gap it resolves.** Never call a tool "to be
  thorough" or "in case it's useful" — if Reasoning didn't name the gap, don't
  take the action.
- **Observation** — what the result actually showed (quote it; don't paraphrase
  into a conclusion).

Repeat until the question is answered. The stopping condition is "no remaining
unknown blocks the answer", not a fixed step count.

## Discipline

- **Look up factual claims rather than guess.** When a step needs a fact, get it
  with a tool. **Never fill a gap with plausible prior knowledge** — that defeats
  the point of investigating.
- If you catch yourself about to act without a named gap, stop and write the
  Reasoning first. If you can't name the gap, you don't need the action.

## Output
- the full step-by-step loop in Reasoning / Action / Observation format
- a **Final output** section whose every claim traces to a specific Observation

## Related
When a claim needs stronger sourcing, hand it to `compass-ground-evidence`. When
you need to check exactly one named assumption in a bounded number of steps, use
`compass-verify-assumptions` (hard-capped at 3 steps).
