---
type: stage
title: score
order: 4
confidence: self-assess-backed
description: Applies the risk model to each enriched record and attaches a score plus model version.
tags:
  - lane:slow
---

Consumes only enriched records. A record arriving without provenance is
scored anyway today; that is the defect `enrich-missing-provenance-check`
tracks.
