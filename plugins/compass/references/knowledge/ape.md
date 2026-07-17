---
type: prompting-technique
title: Automatic Prompt Engineer (APE)
description: Generate several candidate prompts with distinct framings, score each against test cases, select the best objectively.
resource: ../examples/ape.prompt.md
tags: [compass-optimize-instruction]
timestamp: 2026-07-15T00:00:00Z
---

# APE — Automatic Prompt Engineer

For a recurring task needing an optimized, reusable instruction:
generate 5 candidate prompts with genuinely different framings
(rule-based, example-based, definition-based, question-based,
chain-of-thought-based), score each against real test cases, select
objectively rather than by feel.

## Mechanism

5 candidates, one per named framing → score each against every test
case in a table → select the highest scorer, with an explicit rationale
for why it outperforms the others.

## When to apply

- A recurring task needs an optimized, reusable instruction
- Framing sensitivity is suspected and manual iteration is inefficient

## Examples

### In `../examples/ape.prompt.md`

5 differently-framed classifier prompts scored against 5 labeled test
cases, best one selected by raw score.

### In werkstoff

`compass-explore-branches`'s own Score phase
(`plugins/compass/workflows/explore-branches-scan.js`) generalizes
APE's generate-then-score-objectively principle from prompt candidates
to *approach* candidates — both refuse to pick a winner by feel,
requiring an explicit scored comparison first.
`compass-optimize-instruction` is APE's dedicated skill, applying the
mechanism to its original domain (candidate instructions) rather than
the generalized one.
