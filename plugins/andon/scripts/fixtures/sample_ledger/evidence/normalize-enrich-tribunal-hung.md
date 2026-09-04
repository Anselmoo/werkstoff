---
type: evidence
title: "tribunal hung on whether an inferred UTC offset satisfies the contract"
wire: normalize->enrich
strategy: a
verdict: unknown
tags:
  - strategy:a
---

Defender: every emitted record does carry an offset, so the contract's literal
text is met. Challenger: the offset is inferred from the partner's registered
region for ~11% of records, and the contract exists precisely to keep inferred
values out of `enrich`.

The adjudicator scored the contract criterion neither pass nor fail. A hung
verdict is `unknown`, not green -- the loop refuses to advance past it, and the
board draws the wire amber rather than dashed because verification was
attempted and did not settle.
