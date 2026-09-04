---
type: evidence
title: "every manifested file is read exactly once, proven as an invariant"
wire: ingest->normalize
strategy: f
verdict: green
tags:
  - strategy:f
---

Property test over 10k generated manifests: for every landed file, the number
of normalize reads is exactly one. Also the evidence that closed
`ingest-schema-drift-detector`, which links to this doc through `resolved_by`.
