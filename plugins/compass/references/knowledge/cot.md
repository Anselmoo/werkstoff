---
type: prompting-technique
title: Chain-of-Thought
description: Elicit intermediate reasoning steps before the final answer to reduce arithmetic and multi-step logic errors.
resource: ../examples/cot.prompt.md
tags: [escalation-rung-2, compass-reason-verify, default]
timestamp: 2026-07-15T00:00:00Z
---

# Chain-of-Thought (CoT)

The default reasoning rung above zero-shot: requires explicit
step-by-step reasoning before the final answer, making intermediate
errors visible and correctable instead of buried inside a single
unexamined leap.

## Mechanism

Explicit instruction to reason before answering ("think step by step"),
labeled steps (Step 1, Step 2, …), and a clearly marked final answer —
zero-shot often gets the setup right and the arithmetic wrong; labeling
steps forces each intermediate value to actually be computed.

## When to apply

- Multi-step arithmetic or logic with dependent intermediate values
- Tasks where zero-shot's setup is right but its arithmetic drifts

## Examples

### In `../examples/cot.prompt.md`

A multi-item word problem (apples + oranges + change) with 4 labeled
calculation steps.

### In werkstoff

`quality-assertion-audit`'s mutation-reasoning step
(`plugins/quality/workflows/assertion-audit-scan.js`) is CoT-shaped in
spirit: the agent must reason from a proposed mutation to whether the
existing test suite would catch it, an intermediate inferential chain
(read the mutation → read the test → trace whether the assertion would
fail) that a direct "yes/no" verdict would silently skip past. `compass-reason-verify`
is CoT's dedicated rung.
