---
type: gap
title: "landing zone accepts a feed whose column set changed without warning"
stage: ingest
kind: feature
status: closed
blast_radius: local+reversible
resolved_by: "[[evidence/ingest-normalize-property-proof]]"
tags:
  - kind:feature
  - status:closed
  - blast-radius:local+reversible
---

Closed in cycle 1. Kept in the fixture on purpose: a closed gap must not
appear in `open_gaps`, must not raise a stage's badge count, and must not
move the cursor.
