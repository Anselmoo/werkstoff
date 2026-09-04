---
type: gap
title: "normalize infers a UTC offset when the feed omits one"
stage: normalize
kind: feature
status: open
blast_radius: local+reversible
proposal: {"summary": "Reject a record with no explicit offset instead of inferring one from the partner's registered region.", "touches": ["normalize/tz.py"]}
tags:
  - kind:feature
  - status:open
  - blast-radius:local+reversible
---

The normalize->enrich contract says every emitted record carries an explicit
offset. Inferring one satisfies the letter of the contract and violates its
intent -- which is why the tribunal on that wire hung rather than returning
green.
