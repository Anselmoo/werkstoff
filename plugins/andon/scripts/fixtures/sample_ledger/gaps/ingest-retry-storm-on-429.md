---
type: gap
title: "ingest retries a 429 immediately, with no backoff"
stage: ingest
kind: bug
status: open
blast_radius: local+reversible
proposal: {"summary": "Add exponential backoff with jitter to the partner-feed fetcher.", "touches": ["ingest/fetch.py"]}
tags:
  - kind:bug
  - status:open
  - blast-radius:local+reversible
---

Contained entirely inside the fetcher and trivially revertible -- the reason
this one is `local+reversible` while the provenance gap two stages down is
not.
