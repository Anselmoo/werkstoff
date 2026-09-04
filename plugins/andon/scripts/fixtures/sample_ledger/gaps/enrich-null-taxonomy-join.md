---
type: gap
title: "taxonomy join drops records whose category is null instead of bucketing them"
stage: enrich
kind: bug
status: open
blast_radius: hard-to-reverse
proposal: {"summary": "Bucket null categories into `uncategorised` rather than dropping the record.", "touches": ["enrich/taxonomy.py"]}
tags:
  - kind:bug
  - status:open
  - blast-radius:hard-to-reverse
---

An inner join where an outer join was meant. Records already dropped in past
runs cannot be recovered from the serving store, which is what makes this
hard to reverse rather than local.
