---
type: gap
title: "score resolves the risk model at runtime instead of pinning a version"
stage: score
kind: bug
status: open
blast_radius: hard-to-reverse
proposal: {"summary": "Pin the model artifact by digest in the stage manifest and fail the run when it is absent.", "touches": ["score/model.py", "score/manifest.toml"]}
tags:
  - kind:bug
  - status:open
  - blast-radius:hard-to-reverse
---

Two runs of the same input can produce different scores, so no already-published
score can be reproduced after the fact.
