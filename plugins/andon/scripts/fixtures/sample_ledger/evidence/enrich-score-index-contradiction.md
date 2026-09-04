---
type: evidence
title: "structural index has no edge from enrich to score's intake"
wire: enrich->score
strategy: e
verdict: red
tier: 1
non_overridable: true
tags:
  - strategy:e
  - tier:1
---

The ledger claims `enrich` hands provenance-bearing records to `score`. The
symbol index built from the repository contains no call edge from
`enrich/join.py` into `score/intake.py` at all -- the two stages communicate
only through the serving store, so nothing enforces the contract at the
handoff.

Tier 1: the index contradicts the claimed edge itself, not the quality of a
fix. `check_stop_conditions()` has no parameter that can waive this.
