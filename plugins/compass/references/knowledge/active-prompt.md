---
type: prompting-technique
title: Active-Prompt
description: Score confidence explicitly and flag the most uncertain/ambiguous elements rather than silently picking an interpretation.
resource: ../examples/active-prompt.prompt.md
tags: [compass-clarify-scope]
timestamp: 2026-07-15T00:00:00Z
---

# Active-Prompt

Originally: select which candidate examples to hand-label by
uncertainty (the lowest-confidence predictions carry the most
information). `compass-clarify-scope` generalizes the mechanism from
example-selection to scope-clarification: score confidence on every
ambiguous element of a task, surface the lowest-confidence ones first.

## Mechanism

Zero-shot pre-screen every candidate/ambiguous element with a
confidence score; rank ascending by confidence; the lowest-confidence
items are the ones worth spending clarification budget on.

## When to apply

- Ambiguous task phrasing where a silent default interpretation would
  be risky
- A budget exists (time, examples, clarifying questions) and it should
  go to the highest-uncertainty items first

## Examples

### In `../examples/active-prompt.prompt.md`

Selecting which unlabeled classifier examples to hand-label, ranked by
model uncertainty on a zero-shot pre-screen.

### In werkstoff

`self-assess-docs-drift`'s confidence field
(`plugins/self-assess/workflows/docs-drift-scan.js`, `CLAIMS_SCHEMA`'s
`confidence: High|Medium|Low`) is the same underlying discipline: every
claim carries an explicit uncertainty score rather than being reported
as flatly true or false, and the report surfaces High-confidence
contradictions first (analogous to active-prompt's ascending-uncertainty
sort, inverted for reporting priority). `compass-clarify-scope`'s Step
2 applies active-prompt's confidence-table mechanism directly to
scope-ambiguity elements.
