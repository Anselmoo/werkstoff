---
name: compass-summarize-trace
description: >-
  After a compass-solve pipeline finishes, produces a compact written record for
  handoff, PR comment, or documentation — exactly 7 sections covering what was
  asked, assumed, weighed, run, produced, revised, and NOT done. Use when a
  finished multi-stage run needs to be captured: "summarize what we did",
  "write this up for the PR", "hand this off", "document the run", after
  compass-solve completes.
---

# compass-summarize-trace

Turn a completed `compass-solve` run into a fixed 7-section record, then
**validate structure with the guard**.

`GUARD="python3 ${CLAUDE_PLUGIN_ROOT}/scripts/compass.py"`

## The 7 sections (exact order)

1. **What was asked**
2. **What was assumed**
3. **Approaches weighed** — **omit this section ENTIRELY if Explore did not run.**
   Do not leave it empty; remove it.
4. **What ran** — a table listing **every stage from `dag.stages`**.
5. **What was produced**
6. **What was revised** — **always present, even when nothing was revised. If
   nothing changed, say so explicitly.**
7. **What was NOT done**

Follow with a **completeness score table**.

## Validate

The `explore_ran` flag is a first-class gating field the guard branches on:

```
echo '{
  "explore_ran": false,
  "dag_stages": ["gather","draft","check"],
  "sections": [
    {"title":"What was asked","body":"…"},
    {"title":"What was assumed","body":"…"},
    {"title":"What ran","body":"…","stage_ids":["gather","draft","check"]},
    {"title":"What was produced","body":"…"},
    {"title":"What was revised","body":"Nothing was revised: all criteria scored above threshold."},
    {"title":"What was NOT done","body":"…"}
  ]
}' | $GUARD trace -
```

The guard enforces: exactly the right sections in order, "Approaches weighed"
omitted iff Explore did not run, "What was revised" present and non-empty, and
every `dag_stages` id listed under "What ran". A non-zero exit means the structure
is wrong — fix it; the trace's value is its fixed shape.

## Output
- the 7 (or 6, if Explore was skipped) sections in order
- the completeness score table
