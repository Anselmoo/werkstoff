---
type: evidence
title: "oracle-gap V&V on the landing-zone row counts"
wire: ingest->normalize
strategy: b
verdict: green
tags:
  - strategy:b
---

Row counts and checksum totals reconciled against the partner manifest for
30 consecutive days of replayed feeds; the largest gap between the manifest
oracle and the landed count was 0 rows.
