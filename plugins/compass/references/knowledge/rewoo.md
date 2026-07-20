---
type: prompting-technique
title: ReWOO
description: Plan every tool call upfront in one pass, execute them all, then synthesize — cheaper than interleaved reasoning when tool calls are expensive or slow.
resource: ../examples/rewoo.prompt.md
tags: [compass-investigate-dynamically]
timestamp: 2026-07-16T00:00:00Z
---

# ReWOO — Reasoning WithOut Observation

For tasks where tool calls are expensive, slow, or rate-limited and the
plan doesn't need to adapt after every single result: generate the full
tool-call plan upfront in one pass, execute every call, then synthesize —
contrasting with ReAct/ART's interleaved reasoning-per-step.

## Mechanism

`Plan:` (the full list of tool calls, each referencing prior calls'
placeholder results, e.g. `#E1`, `#E2`) → `Execute:` (run every call in
sequence without re-reasoning between them) → `Solve:` (synthesize the
final answer from all results), rather than one Reasoning/Action/Observation
triple per step.

## When to apply

- Tool calls are expensive, slow, or rate-limited — planning once avoids
  paying a reasoning pass before every single call
- The plan genuinely doesn't need to adapt mid-execution — if step 3's
  result could change step 4, use ReAct/ART instead

## Examples

### In `../examples/rewoo.prompt.md`

A multi-lookup research task planned as a fixed sequence of calls up
front, executed without re-reasoning, then synthesized.

### In werkstoff

**`confab-dependency-audit`'s Step 0 is ReWOO in spirit**: "The workflow
script has no filesystem access, so gather everything first" — every
manifest file and registry to check is assembled into one plan before
any tool call executes, then Step 1 fires all registry lookups in
parallel (one finder per manifest type), with no re-planning between
calls. `compass-investigate-dynamically` documents this as the
cost-sensitive end of its escalation ladder, next to ReAct/ART's
adaptive interleaving.
