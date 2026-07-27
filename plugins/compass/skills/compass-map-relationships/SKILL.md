---
name: compass-map-relationships
description: >-
  Answers a question that turns on entity/dependency/causal structure by
  extracting indexed relationship triples and traversing them hop by hop, citing
  the triple index at every hop. Use when the answer requires following a chain
  through named entities and relationships: "how does A affect D through the
  chain", "trace the dependency path", "who reports to whom", "what causes what
  here", multi-hop "why" questions, or a compass-solve stage that needs graph
  traversal.
---

# compass-map-relationships

Extract the relevant triples, pick a start node, traverse, and **validate with the
guard**. The guard enforces the triple ceiling and that every hop cites a real
triple.

`GUARD="python3 ${CLAUDE_PLUGIN_ROOT}/scripts/compass.py"`

## Process

1. **Extract only relationships relevant to the question.** Do not dump the whole
   graph.
2. Build **indexed triples**: numbered `{index, subject, predicate, object}`.
3. **The table MUST stay at roughly 50 triples or fewer.** If the relevant graph
   is larger, **pre-filter to the relevant subgraph** — do not inject the full
   graph. The guard rejects more than 50.
4. Choose a **start_node** and state why.
5. **Traverse**: ordered `{hop, triple_index, predicate, to}`. **Every hop MUST
   cite the triple index it uses.** Never state a relationship as true without
   pointing at its numbered triple.

## Validate

```
echo '{"triples":[
  {"index":1,"subject":"A","predicate":"depends_on","object":"B"},
  {"index":2,"subject":"B","predicate":"calls","object":"C"}
],"traversal":[
  {"hop":1,"triple_index":1,"predicate":"depends_on","to":"B"},
  {"hop":2,"triple_index":2,"predicate":"calls","to":"C"}
]}' | $GUARD map -
```
A non-zero exit means either the triple count exceeded the ceiling or a hop cited
a triple index not in the table — fix it before answering.

## Output
- the indexed triple table
- start_node + reason
- the traversal, each hop citing its triple index
- the final answer stated with the complete citation path
