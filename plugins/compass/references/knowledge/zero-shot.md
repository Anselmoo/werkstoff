---
type: prompting-technique
title: Zero-shot
description: Direct task instruction without examples or reasoning scaffolding, relying on pre-trained knowledge of the task domain.
resource: ../examples/zero-shot.prompt.md
tags: [escalation-rung-0, compass-reason-verify, baseline]
timestamp: 2026-07-15T00:00:00Z
---

# Zero-shot

The no-extra-structure baseline. Applies when a task is well-defined,
common, and single-turn — adding a reasoning scaffold or examples would
be pure overhead, not accuracy.

## Mechanism

Role statement + specific output-format constraint, nothing else. No
`<examples>` block, no reasoning loop, no external retrieval.

## When to apply

- Well-defined tasks with clear, common output formats
- Domains where pre-trained coverage is reliable
- Single-turn, single-output tasks with no dependencies

## Examples

### In `../examples/zero-shot.prompt.md`

Summarizing a legal clause in plain language — the output structure
(4 fixed points) is fully specified, so no worked example is needed to
disambiguate it.

### In werkstoff

`self-assess-status`'s `SKILL.md` (`plugins/self-assess/skills/self-assess-status/SKILL.md`)
is a clean zero-shot skill: a direct, single-pass instruction producing
a fixed 3-line verdict (furthest completed check / what's stale / next
skill), no examples, no reasoning chain, no fan-out — the task is exactly
the shape zero-shot exists for. `compass-reason-verify` treats this as
rung 0: default to it, escalate only when a task's own shape demands more.
