---
type: prompting-technique
title: Prompt Chaining
description: Run a task as a sequence of independently-verifiable stages, each stage's output feeding the next as an explicit contract.
resource: ../examples/prompt-chaining.prompt.md
tags: [compass-decompose-chain]
timestamp: 2026-07-15T00:00:00Z
---

# Prompt Chaining

Decompose long-form or complex work into stages, each producing an
independently verifiable artifact that feeds the next stage exactly —
no implicit context carried forward. Errors caught at an early stage
are cheap to fix; caught only at the end, they cascade into a full
rewrite.

## Mechanism

A fixed sequence of stages (e.g. extract-facts → build-outline →
write-draft), each stage's prompt explicitly scoped to only the prior
stage's output, never the original raw input directly.

## When to apply

- Long-form or complex output where each stage's quality can be checked
  independently
- Errors caught early are cheap; caught late they cascade

## Examples

### In `../examples/prompt-chaining.prompt.md`

A 3-stage research-to-draft pipeline: extract facts → build an
outline mapped to those facts → write the article from the outline only.

### In werkstoff

`code-modernization`'s own 8-command pipeline (assess → map →
extract-rules → brief → reimagine → transform → harden) is
prompt-chaining at plugin-architecture scale, and `self-assess`'s
preflight-feeds-everything-else pattern (`PREFLIGHT.md` read by every
downstream skill's Step 0) is the same discipline at a smaller grain —
each stage's artifact is the *only* thing the next stage is allowed to
depend on. `compass-decompose-chain`'s `dependsOn`-per-stage contract
(`plugins/compass/skills/compass-decompose-chain/SKILL.md`) formalizes
this as a reusable mechanism `compass-solve` can execute generically,
for any task, not just plugin-development pipelines.
