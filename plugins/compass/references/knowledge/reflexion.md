---
type: prompting-technique
title: Reflexion
description: Draft, score against explicit numbered criteria, then revise only what scored below threshold — preventing anchoring on a flawed first draft.
resource: ../examples/reflexion.prompt.md
tags: [compass-draft-revise]
timestamp: 2026-07-15T00:00:00Z
---

# Reflexion

Write a first draft, score it against an explicit numbered criteria
table (1-5 per criterion), revise only what scored at or below
threshold, list what changed. Prevents the common failure of a
revision that "reads differently" while repeating the same structural
flaws, by forcing an objective external critique before touching
anything.

## Mechanism

Stage 1 draft → Stage 2 score each criterion 1-5 with a required-fix
sentence for anything ≤3 → Stage 3 revise only the flagged criteria,
list changes as bullets.

## When to apply

- Document/artifact quality matters and a first-draft pass is
  insufficient
- An explicit, checkable criteria list exists or can be elicited

## Examples

### In `../examples/reflexion.prompt.md`

A 7-criterion essay-quality table (thesis clarity, paragraph focus,
evidence, transitions, conclusion, tone, sentence length), revised only
where scores were ≤3.

### In werkstoff

**This session's own Task 8 subagent-driven-development loop is a
live, literal Reflexion cycle**: an implementer drafts, a fresh
reviewer subagent scores the diff against the brief (Critical/
Important/Minor, spec-compliance verdict), and only the flagged issues
get a fix dispatch — never a wholesale redo
(`.superpowers/sdd/sa-task-8-report.md` documents exactly this).
`compass-draft-revise` formalizes the same score-then-selectively-revise
discipline as a standalone skill for any artifact, not just code diffs.
