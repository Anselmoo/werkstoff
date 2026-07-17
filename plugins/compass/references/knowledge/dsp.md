---
type: prompting-technique
title: Demonstrate-Search-Predict (DSP)
description: Decompose a multi-hop question into sub-questions, retrieve a fact per sub-question, then synthesize.
resource: ../examples/dsp.prompt.md
tags: [compass-decompose-chain]
timestamp: 2026-07-15T00:00:00Z
---

# DSP — Demonstrate-Search-Predict

For questions that combine information from separate sources where a
single-shot retrieval can't answer them (the first retrieval's target
depends on an earlier sub-question's answer): decompose into 2-4
sub-questions, retrieve one fact per sub-question with its source, then
synthesize using only those facts, citing which sub-question each part
of the answer came from.

## Mechanism

Decompose → per-sub-question retrieve-with-source (table) → synthesize
citing sub-question numbers, never introducing facts not retrieved in
the prior step.

## When to apply

- Multi-hop questions combining information from separate sources
- A single-shot retrieval genuinely cannot answer the question

## Examples

### In `../examples/dsp.prompt.md`

"Which country founded the most-used smartphone OS's maker, and its
GDP?" — 4 chained sub-questions, each retrieval depending on the prior
answer.

### In werkstoff

`self-assess-docs-drift`'s Find phase (`plugins/self-assess/workflows/docs-drift-scan.js`)
is decompose-then-verify-per-piece in spirit: each doc file's claims
are extracted and *independently* checked against code before the
overall report synthesizes contradictions — no claim's verdict depends
on trusting an earlier claim's verdict, but the overall report can't be
assembled until every sub-check has run, the same "can't single-shot
this, decompose first" structural necessity DSP formalizes.
`compass-decompose-chain` is DSP's (and prompt-chaining's) shared
dedicated skill.
