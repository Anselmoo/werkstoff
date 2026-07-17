---
type: prompting-technique
title: Multimodal Chain-of-Thought
description: Describe everything visible before reasoning, then reason, then answer — preventing answer-first-justify-later errors on image/diagram input.
resource: ../examples/multimodal-cot.prompt.md
tags: [triggered-mode, compass-reason-verify]
timestamp: 2026-07-15T00:00:00Z
---

# Multimodal Chain-of-Thought

A triggered mode, not an escalation rung: whenever input includes an
image or diagram, describe it fully before attempting to answer,
preventing the common failure of generating a confident answer before
actually reading the visual content.

## Mechanism

Four steps: Describe (full visual inventory, no answering yet) →
Identify relevant elements → Reason from only the identified elements →
Answer, citing the reasoning step that supports it.

## When to apply

- Input includes an image or diagram requiring interpretation
- A direct answer would skip critical visual-reading steps

## Examples

### In `../examples/multimodal-cot.prompt.md`

Reading a network-topology diagram to compute maximum throughput —
describe all edges and bandwidths first, then reason about paths.

### In werkstoff

No skill in this repo currently takes image/diagram input directly —
an honest gap, not a forced example (OKF's own consumption model
tolerates this: `compass-reason-verify`'s SKILL.md documents this mode
for when a future task supplies one, e.g. a user pasting a screenshot
of an architecture diagram into a `compass-solve` run). The closest
structural analog is `self-assess-stage-map`'s interactive
`STAGE_MAP.html` viewer (`plugins/self-assess/assets/topology-viewer.html`)
— a visual artifact a *human* reads before trusting the accompanying
markdown report, the same describe-before-conclude discipline applied
outside the model itself.
