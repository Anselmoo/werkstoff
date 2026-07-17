---
type: prompting-technique
title: Few-shot
description: Anchor an ambiguous output format on 2-5 diverse real examples rather than describing it in prose.
resource: ../examples/few-shot.prompt.md
tags: [escalation-rung-1, compass-calibrate-format]
timestamp: 2026-07-15T00:00:00Z
---

# Few-shot

Provide diverse input/output examples to demonstrate an expected
format, style, or domain-specific decision boundary — used when the
output format is ambiguous without a worked demonstration.

## Mechanism

An `<examples>` block of 2-5 `<example><input>...<output>...</example>`
pairs covering diverse, non-trivial cases (not toy demonstrations that
all look alike) — the decision boundary lives in the examples, not the
prose around them.

## When to apply

- Niche or custom output format the model hasn't seen frequently
- Domain-specific classification with non-standard category labels
- Style/tone matching against provided examples

## Examples

### In `../examples/few-shot.prompt.md`

A support-ticket classifier where the boundary between `technical` and
`feature_request` is genuinely ambiguous without seeing worked cases.

### In werkstoff

`plugins/self-assess/agents/ci-topology-auditor.md`'s frontmatter
`description` field carries 4 full `<example>` blocks (redundant-remote
audit, mirror-risk PR review, CI-doc drift, origin/upstream swap
verification) — this is few-shot applied to *agent triggering itself*:
Claude Code decides whether to dispatch this agent partly by matching
the user's request against these worked scenarios, the same mechanism
`compass-calibrate-format` applies to output-format calibration.
`compass-calibrate-format` is this technique's dedicated skill.
