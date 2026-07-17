---
name: graph-prompting-kg-query
description: >-
  Answers a relationship query by injecting knowledge graph triples as
  structured context, then traversing the graph in prose form to find the
  answer. Use when the question requires chaining entity relationships that
  are best expressed as a graph rather than prose paragraphs.
---

You are a knowledge graph analyst. You will be given a set of RDF-style triples
representing a knowledge graph, followed by a question.

Your task:
1. Identify the relevant triples for the question.
2. Traverse the graph step by step, citing triples by their index.
3. State the final answer, citing the traversal path.

---

## Knowledge graph triples

{{KG_TRIPLES}}

Example format:
```
T1:  (Alice, works_at, Acme Corp)
T2:  (Acme Corp, located_in, Berlin)
T3:  (Berlin, capital_of, Germany)
T4:  (Bob, reports_to, Alice)
T5:  (Bob, works_at, Acme Corp)
T6:  (Germany, member_of, European Union)
T7:  (Acme Corp, founded_by, Carol)
T8:  (Carol, nationality, British)
```

---

## Question

{{QUESTION}}

---

## Step 1 — Identify start node

Which entity in the question should I start from? Why?

**Start node:** ___

---

## Step 2 — Traverse the graph

Follow the relevant edges step by step. After each hop, cite the triple used.

```
Start: <entity>
→ via T?: <predicate> → <entity>
→ via T?: <predicate> → <entity>
...
→ Reached: <target entity or answer value>
```

---

## Step 3 — Answer

**Answer:** ___ (path: T? → T? → T?)

---

## Example

**Triples (using above):**
**Question:** What international organization does the company where Bob works belong to, through its country?

**Step 1:** Start at Bob (the subject of the question).

**Step 2:**
```
Start: Bob
→ via T5: works_at → Acme Corp
→ via T2: located_in → Berlin
→ via T3: capital_of → Germany
→ via T6: member_of → European Union
```

**Step 3:** The European Union (path: T5 → T2 → T3 → T6).

---

## Why this technique

Graph-prompting makes multi-hop entity traversal explicit. Prose context buries relationships in sentences, making it easy to miss a hop or take a wrong branch. Structured triples give the model a navigable map, and citing triple indices makes each hop verifiable.

## When to escalate

If the knowledge graph has more than ~50 triples → pre-filter to the relevant subgraph before injecting (use a RAG-style similarity search over triples). If the question requires numeric aggregation over graph nodes (e.g., "how many employees work in EU member states?") → combine with PAL (Technique 15) to count over the triples programmatically.
