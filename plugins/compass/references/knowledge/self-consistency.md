---
type: prompting-technique
title: Self-Consistency
description: Run multiple independent reasoning paths and take the majority answer, catching cases where one path makes an early wrong assumption.
resource: ../examples/self-consistency.prompt.md
tags: [escalation-rung-3a, compass-reason-verify, parallel]
timestamp: 2026-07-15T00:00:00Z
---

# Self-Consistency

Escalation from CoT for tasks with a unique correct answer where a
single wrong early assumption is a real risk: reason through the
problem 3 times independently, using different strategies, and take
the majority result.

## Mechanism

3 independent attempts, each with a distinct named strategy (e.g.
forward deduction / backward-from-options / constraint-mapping), no
attempt sees another's reasoning; majority vote (or, if all 3 disagree,
the strongest individual chain) is the final answer.

## When to apply

- A unique correct answer exists
- A single wrong early assumption is a real, plausible risk

## Examples

### In `../examples/self-consistency.prompt.md`

A logic puzzle solved 3 independent ways (forward deduction, backward
from options, constraint mapping), majority-voted.

### In werkstoff

This is, structurally, the **adversarial-verify tier every self-assess
and quality Workflow script already implements** — e.g.
`plugins/self-assess/workflows/stage-map-scan.js`'s Verify phase
dispatches one independent reviewer per candidate wire who must
re-derive the verdict from the cited code itself rather than trusting
the Find phase's claim, and `plugins/quality/workflows/lint-audit-scan.js`
adds a *second*, independent re-confirmation tier for High-severity
findings — the same "don't trust one path, get an independent read"
principle self-consistency formalizes for open-ended reasoning tasks.
`compass-reason-verify`'s `workflows/reason-verify-scan.js` implements
this rung directly with 3 parallel `reasoning-path` agents.
