---
type: stage
title: ingest
order: 1
confidence: self-assess-backed
description: Pulls raw partner feeds off object storage and writes them untouched to the landing zone.
tags:
  - lane:fast
---

Entry point of the stream. Owns retry, dedupe and the landing-zone manifest.
Nothing downstream may read a file this stage has not manifested.
