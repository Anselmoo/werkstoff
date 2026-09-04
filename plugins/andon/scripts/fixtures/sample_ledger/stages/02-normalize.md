---
type: stage
title: normalize
order: 2
confidence: self-assess-backed
description: Coerces every landed record into the canonical unit/timezone/schema triple.
tags:
  - lane:fast
---

The only stage allowed to change a record's units. Its contract with `enrich`
is that every emitted record carries an explicit unit and an explicit UTC
offset -- never an inferred one.
