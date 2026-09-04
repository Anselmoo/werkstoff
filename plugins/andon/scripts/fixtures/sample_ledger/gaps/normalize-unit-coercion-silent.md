---
type: gap
title: "unit coercion falls back to the source unit without logging"
stage: normalize
kind: bug
status: open
blast_radius: hard-to-reverse
proposal: {"summary": "Raise on an unknown unit rather than passing the source unit through untouched.", "touches": ["normalize/units.py"]}
tags:
  - kind:bug
  - status:open
  - blast-radius:hard-to-reverse
---

A silent fallback: the record still validates downstream, so nothing errors,
and the mixed-unit rows are indistinguishable from correct ones once they
reach the serving store.
