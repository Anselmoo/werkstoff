---
type: gap
title: "enrich emits records with no provenance row, and score accepts them"
stage: enrich
kind: wire
status: open
blast_radius: shared-state-visible
on_constraint: true
proposal: {"summary": "Fail the enrich->score handoff when a record has no provenance row, rather than defaulting provenance to the empty string.", "touches": ["enrich/join.py", "score/intake.py"]}
tags:
  - kind:wire
  - status:open
  - blast-radius:shared-state-visible
---

The enrich->score contract says every scored record can be traced back to the
partner feed it came from. `join.py` left-joins the provenance table and keeps
the row when the join misses, so ~4% of scored records carry an empty
provenance string that the serving store then publishes as fact.

This is the gap the cursor is parked on, and the wire beneath it is the one
the structural index contradicted.
