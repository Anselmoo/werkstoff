---
name: compass-draft-revise
description: >-
  Scores an already-drafted artifact 1-5 against explicit numbered criteria and
  selectively revises only the criteria that fall at or below threshold, leaving
  what already works untouched — then reports exactly what changed. Use when a
  draft exists and needs targeted iteration rather than a rewrite: "score this
  against these criteria and fix what's weak", "revise selectively", "which parts
  fall short", "iterate on this draft", or the Revise phase of compass-solve.
---

# compass-draft-revise

Score, then revise **only** what fails, then report. The guard enforces the scale,
the threshold, the selectivity, and the escalation in code.

`GUARD="python3 ${CLAUDE_PLUGIN_ROOT}/scripts/compass.py"`

## Inputs
- an already-drafted artifact
- 3-7 explicit numbered success criteria

## 1. Score and plan (guarded)

Score the draft **1-5 against every criterion independently**, then:

```
echo '{"threshold":3,"criteria":[
  {"criterion":"covers all cases","score":2},
  {"criterion":"correct tone","score":4},
  {"criterion":"no dead links","score":5}
]}' | $GUARD revise-plan -
```

- **Default threshold is 3** on the 1-5 scale (omit `threshold` to use it).
- The guard returns `revise` (criteria at or below threshold — the only ones you
  may touch), `keep_untouched` (above threshold — **MUST NOT modify**), and
  `needs_second_cycle`.

## 2. Revise selectively

Revise **only** the criteria in `revise`. Revising is not rewriting: leave every
above-threshold criterion's content exactly as it was.

## 3. Report changes (guarded)

Never present a revision without a changes list — one bullet per required fix.

```
echo '{"plan":{"revise":[{"criterion":"covers all cases"}],"keep_untouched":[{"criterion":"correct tone"},{"criterion":"no dead links"}]},
       "changes":["Added the empty-input case to section 2"],
       "touched_criteria":["covers all cases"]}' | $GUARD revise-report -
```
A non-zero exit means either the changes list was missing or an above-threshold
criterion was modified — both are violations to fix.

## 4. Escalate if needed

**If the revised draft still scores at or below threshold on any criterion, run a
second score-then-revise cycle on the revised draft.** The hard cap is 2 cycles.

## Output
- the revised artifact (only at/below-threshold criteria addressed)
- the changes list, one bullet per fix
