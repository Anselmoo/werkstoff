---
name: compass-calibrate-format
description: >-
  Pins down an ambiguous output format, style, tone, or schema by anchoring it to
  2-5 concrete input/output examples instead of more prose. Use when prose keeps
  under- or over-specifying the target shape: "match this format", "I can't
  describe it but here's an example", "make it look like these", a non-standard
  schema, tone, or layout that's hard to state in words, or a compass-solve stage
  whose output shape is fuzzy.
---

# compass-calibrate-format

When words keep missing the target shape, switch to examples. The guard enforces
the example-count band and the diversity rule.

`GUARD="python3 ${CLAUDE_PLUGIN_ROOT}/scripts/compass.py"`

## Assemble the example set

- **Source examples from real prior outputs first.** Only construct examples if no
  real outputs exist.
- Use **2-5 examples total.** Fewer than 2 is not few-shot anchoring; more than 5
  usually means the format is still underspecified — tighten it instead.
- **Do not use all-alike examples.** At least one must sit **near a boundary**
  between plausible interpretations, so the examples actually pin the decision.
- If you must **construct** the set, include a **happy path** and **at least one
  edge case**, and mark the boundary example with `near_boundary: true` and each
  example's `kind` (`happy-path` / `edge-case`).

## Validate

Real examples:
```
echo '{"constructed":false,"examples":[{"in":"x","out":"y"},{"in":"a","out":"b"}]}' | $GUARD calibrate -
```
Constructed examples (diversity enforced):
```
echo '{"constructed":true,"examples":[
  {"kind":"happy-path","in":"normal","out":"…","near_boundary":false},
  {"kind":"edge-case","in":"empty","out":"…","near_boundary":true}
]}' | $GUARD calibrate -
```
A non-zero exit means too few/many examples, or a constructed set missing a happy
path, an edge case, or a boundary example — fix before producing the artifact.

## Output
- a formatted artifact matching the decision boundary the anchored examples set
