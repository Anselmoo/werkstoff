---
name: compass-decompose-chain
description: >-
  Breaks a scoped problem or selected approach into a 2-5 stage pipeline, each
  stage with an explicit input contract, output contract, and dependsOn list, and
  derives the parallel-safe wave grouping from the dependency graph. Use when a
  task is big enough to need staging with clear hand-offs between steps: "break
  this into steps", "what's the pipeline here", "map the stages", "what depends on
  what", or the Decompose phase of compass-solve.
---

# compass-decompose-chain

Design the stages, then **validate the graph with the guard**. The guard enforces
every structural rule in code and returns the topological waves.

`GUARD="python3 ${CLAUDE_PLUGIN_ROOT}/scripts/compass.py"`

## Design

Produce a table with columns: **id, name, input contract, output contract,
dependsOn**. `dependsOn` is an array of stage ids. Each of these is a first-class
field the executor branches on — none may live in a prose sentence.

## The rules (enforced in code)

- **Between 2 and 5 stages inclusive.** Fewer than 2 means it didn't need
  decomposing; more than 5 means the task itself needs re-scoping.
- **Every stage MUST define input contract, output contract, and a dependsOn
  array.**
- **At least one stage MUST have `dependsOn: []`** — the entry point.
- **No dependsOn may reference a non-existent stage id.**
- **The graph MUST be acyclic** — no stage transitively depends on itself.

## Validate

```
echo '{"stages":[
  {"id":"gather","name":"Gather","input_contract":"raw task","output_contract":"sources","dependsOn":[]},
  {"id":"draft","name":"Draft","input_contract":"sources","output_contract":"draft","dependsOn":["gather"]},
  {"id":"check","name":"Check","input_contract":"sources","output_contract":"issues","dependsOn":["gather"]}
]}' | $GUARD decompose -
```

On success the guard returns `entry_points` and `waves` (the parallel-safe
grouping via Kahn's algorithm). A non-zero exit means a bound, a dangling
reference, or a cycle was violated — fix the plan; do not proceed with an invalid
graph.

## Output
- the stage table
- the parallel-safe wave grouping (from the guard's `waves`)
