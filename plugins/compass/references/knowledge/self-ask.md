---
type: prompting-technique
title: Self-Ask
description: A minimal "do I need a follow-up question?" lookup chain — ReAct's simpler precursor, for a single or short chain of conditional lookups.
resource: ../examples/self-ask.prompt.md
tags: [compass-investigate-dynamically]
timestamp: 2026-07-16T00:00:00Z
---

# Self-Ask

For tasks needing at most a short chain of conditional lookups rather
than a full dynamic tool-selection loop: explicitly ask "are follow-up
questions needed here?", look up each follow-up's answer rather than
guessing it, and repeat until no follow-up remains.

## Mechanism

`Are follow-up questions needed here: Yes/No.` → if yes, `Follow up:
<question>` / `Intermediate answer: <looked up, not guessed>`, repeated
until no follow-up remains → `So the final answer is: <answer>`. ReAct's
historical precursor: no tool-selection library, just a sequential
conditional-lookup chain.

## When to apply

- A single or short chain (2-3 hops) of conditional lookups, not an
  open-ended investigation
- The minimal-mechanism entry point before reaching for full ReAct/ART —
  escalate if the chain grows past 2-3 hops or needs adaptive tool choice

## Examples

### In `../examples/self-ask.prompt.md`

A factual question decomposed into one or two follow-up lookups before
the final answer.

### In werkstoff

**`self-assess-lint-audit`'s Step 0 is a Self-Ask chain**: check
`.claude/house-rules.md` first; if absent, ask the genuine follow-up "is
`CLAUDE.md` there instead?" and use it as a degraded, clearly-labeled
fallback; if neither exists, stop rather than guess a convention. Three
sequential yes/no lookups, no tool-selection library needed —
`compass-investigate-dynamically` documents this as its minimal-mechanism
rung, below ReAct/ART.
