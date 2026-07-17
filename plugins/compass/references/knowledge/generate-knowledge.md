---
type: prompting-technique
title: Generate Knowledge
description: Generate relevant background facts before answering, forcing explicit surfacing of prior knowledge and its uncertainty.
resource: ../examples/generate-knowledge.prompt.md
tags: [compass-clarify-scope, compass-ground-evidence]
timestamp: 2026-07-15T00:00:00Z
---

# Generate Knowledge

Before answering, list the key facts relevant to the task, flagging any
fact held with less than ~90% confidence. Then answer using only those
facts, referenced by number — surfacing what's actually known (and how
confidently) rather than silently blending it into the answer.

## Mechanism

Numbered facts list, ⚠️ flag on any fact below the confidence
threshold; the subsequent answer must reference facts by number and
must explicitly flag if it depended on an uncertain one.

## When to apply

- The answer depends on prior knowledge that might be omitted or
  misremembered if not surfaced explicitly
- Uncertainty about specific facts needs to stay visible, not silently
  assumed

## Examples

### In `../examples/generate-knowledge.prompt.md`

"Why does ice float on water?" answered from 6 explicitly numbered
physical facts, one flagged ⚠️.

### In werkstoff

`self-assess-preflight`'s Check 1 (`plugins/self-assess/skills/self-assess-preflight/SKILL.md`)
generates the facts every downstream skill needs — detected languages,
tool availability, house-rules presence — *before* any analysis skill
runs, exactly generate-knowledge's "surface facts first" discipline
applied at the plugin-architecture level rather than within a single
prompt. `compass-clarify-scope` is this technique's primary mechanism,
generalized from a science question to any vague task's `known_facts`.
