---
type: prompting-technique
title: Graph Prompting
description: Structure relationships as indexed triples before reasoning over them, traverse citing triple indices, answer with the full path.
resource: ../examples/graph-prompting.prompt.md
tags: [compass-map-relationships]
timestamp: 2026-07-15T00:00:00Z
---

# Graph Prompting

For multi-hop entity-relationship questions, inject the relevant
relationships as indexed `(subject, predicate, object)` triples before
reasoning, identify a start node, traverse hop by hop citing which
triple justified each step, and state the answer with its full path —
never buried in prose paragraphs that make a wrong hop invisible.

## Mechanism

Numbered triples (`T1: (Alice, works_at, Acme Corp)`, …) → identify
start node → traverse citing `T?` at each hop → answer with the full
`T? → T? → T?` path.

## When to apply

- Multi-hop entity/dependency/causal traversal (org charts, dependency
  graphs, causal chains)
- Prose would bury or lose relationships a navigable structure makes
  explicit

## Examples

### In `../examples/graph-prompting.prompt.md`

"What international org does the country of the company Bob works at
belong to?" — traversed via 4 cited triples, not a prose paragraph.

### In werkstoff

`self-assess-stage-map`'s actual data model
(`plugins/self-assess/workflows/stage-map-scan.js`, `EDGES_SCHEMA`) is
graph-prompting's real-world analog already running in this repo: every
import edge is a `{from, to, kind}` triple (`kind` ∈ `ref`/`ref/call`/
`childof`, borrowed from Kythe/LSIF vocabulary), and the confirmed-wire
report cites the exact edges that justified each cross-stage
dependency. `compass-map-relationships` generalizes this exact
triple-and-cite discipline from import graphs to any entity-relationship
domain (org charts, causal chains) — the same mechanism, a different
subject matter.
