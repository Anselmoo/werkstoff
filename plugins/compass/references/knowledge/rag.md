---
type: prompting-technique
title: Retrieval-Augmented Generation (RAG)
description: Answer using only retrieved/provided passages, cite every claim, and explicitly refuse when the sources are insufficient.
resource: ../examples/rag.prompt.md
tags: [compass-ground-evidence]
timestamp: 2026-07-15T00:00:00Z
---

# RAG — Retrieval-Augmented Generation

Answer strictly from retrieved passages, never prior knowledge or
inference beyond what's stated; cite every factual claim by passage;
refuse explicitly ("the available documents do not contain sufficient
information to answer this question") rather than confabulating past
the sources' actual coverage.

## Mechanism

Rules stated up front (answer only from passages, cite every claim,
explicit insufficient-information refusal, no silent cross-source
merging unless both sources explicitly support the same point) — the
retrieval step decouples "what the model knows" from "what the source
says," making the answer auditable.

## When to apply

- Grounding answers in a specific knowledge base
- Citations are required and confabulation must be prevented

## Examples

### In `../examples/rag.prompt.md`

Explaining 2023 regional bank failures strictly from two cited FDIC/DFS
passages, each claim tagged `(Passage N)`.

### In werkstoff

`self-assess-docs-drift`'s entire mandate
(`plugins/self-assess/skills/self-assess-docs-drift/SKILL.md`) is RAG's
citation discipline applied to code-verification: every contradiction
report requires `file:line` evidence on *both* the doc side and the
code side, and a claim with no verifiable code counterpart is reported
as "cannot find code either way," never guessed at. `compass-ground-evidence`
generalizes this exact discipline beyond code-vs-docs to any
factual-grounding task, and is RAG's dedicated skill.
