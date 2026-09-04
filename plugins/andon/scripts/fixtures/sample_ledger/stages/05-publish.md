---
type: stage
title: publish
order: 5
confidence: single-package
description: Writes scored records to the serving store and emits the freshness beacon.
tags:
  - lane:fast
---

Terminal stage. No open gaps -- which is exactly why it renders without a
badge: an unbadged stage means "nothing open here", not "not yet looked at".
