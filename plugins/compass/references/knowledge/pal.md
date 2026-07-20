---
type: prompting-technique
title: Program-Aided Language Models (PAL)
description: Offload computation to executable code instead of mental arithmetic in language, for guaranteed precision.
resource: ../examples/pal.prompt.md
tags: [escalation-rung-3b, compass-reason-verify]
timestamp: 2026-07-15T00:00:00Z
---

# PAL — Program-Aided Language Models

Escalation from CoT when arithmetic precision matters more than
reasoning transparency: write code that computes the answer, execute
it, report the result — language-model mental arithmetic accumulates
rounding/carry errors that exact code arithmetic does not.

## Mechanism

A `solve()` function with descriptive variable names and a comment per
line explaining what it represents; call it and print the result; state
the answer in plain language afterward.

## When to apply

- Many variables, conditional logic, large numbers, or long calculation
  chains risking rounding/carry errors
- Arithmetic precision matters more than showing reasoning

## Examples

### In `../examples/pal.prompt.md`

A factory-revenue word problem computed via a Python `solve()` function
rather than mental multiplication chains.

### In werkstoff

`confab-assertion-audit`'s optional real-mutation-tool augmentation
(`plugins/confab/skills/confab-assertion-audit/SKILL.md`) is PAL's
exact principle: when `confab-preflight` finds `mutmut`/Stryker/PIT on
`PATH`, the skill shells out to the real tool for ground-truth mutation
scores instead of LLM-reasoning about whether a test would catch a
mutation — offloading precision-sensitive computation to code, falling
back to reasoning only when no tool is available, and labeling which
mode ran rather than blending them. `compass-reason-verify` is PAL's
dedicated escalation rung for reasoning tasks generally.
