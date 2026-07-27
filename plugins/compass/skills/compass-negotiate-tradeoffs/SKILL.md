---
name: compass-negotiate-tradeoffs
description: >-
  After compass-explore-branches has selected a winner, synthesizes a hybrid that
  combines strengths from 2-3 branches — but only presents it if it actually beats
  every source branch on at least one axis. Use when a single winner leaves value
  on the table and you want the best of several: "can we combine the best of these
  approaches", "what if we merged A and B", "the winner's good but I liked X from
  the runner-up". Runs strictly AFTER branch selection, never as a substitute for
  it.
---

# compass-negotiate-tradeoffs

Synthesize a hybrid from the selected winner and 1-2 runners-up, then **let the
guard decide whether it may be presented**. The precondition and the outperform
gate are enforced in code.

`GUARD="python3 ${CLAUDE_PLUGIN_ROOT}/scripts/compass.py"`

## Precondition

**MUST NOT run before `compass-explore-branches` has already selected a winner.**
This skill runs strictly after selection — never as a way to avoid choosing. The
guard rejects the call if `explore_winner_selected` is false.

## Process

1. Build a **trade-off matrix**: for each source branch, what it gives up and what
   the hybrid preserves.
2. Name and describe the **hybrid approach**.
3. Score the hybrid on **Feasibility, Impact, Risk, each 1-10, against the same
   rubric** used in Explore.
4. State any **genuinely-exclusive conflict** the hybrid could not reconcile, and
   which side it picked.

## Validate (the outperform gate)

```
echo '{"explore_winner_selected":true,
  "sources":[
    {"name":"Winner","feasibility":9,"impact":5,"risk":6},
    {"name":"Runner","feasibility":5,"impact":9,"risk":6}],
  "hybrid":{"feasibility":8,"impact":8,"risk":7}}' | $GUARD negotiate -
```

**The guard refuses (non-zero exit) unless the hybrid outperforms EVERY source on
at least one axis** (higher number on an axis = better; Risk is never inverted in
compass). **If the guard refuses, do not present the hybrid** — report that no
worthwhile hybrid exists and keep the selected winner.

## Output
- the trade-off matrix
- the hybrid name + description
- the score comparison for each source branch and the hybrid
- the verdict (and any unresolved exclusive conflict)
