---
type: gap
title: "the score->publish cutoff has no test at either boundary"
stage: score
kind: wire
status: open
blast_radius: shared-state-visible
proposal: {"summary": "Add boundary tests at the cutoff and one either side, then prove the wire before publish is allowed to read from it.", "touches": ["score/threshold.py", "tests/test_threshold.py"]}
tags:
  - kind:wire
  - status:open
  - blast-radius:shared-state-visible
---

The reason `score->publish` has no evidence doc at all: nothing has ever been
run against that handoff, so the board draws it dashed rather than amber. A
dashed edge is not a weaker amber -- it means no verification has been
attempted.
