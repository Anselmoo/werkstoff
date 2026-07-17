---
name: reflexion-essay-revision
description: >-
  Writes an essay draft, evaluates it against explicit criteria, then
  produces a revised version addressing all identified shortcomings.
  Use when document quality matters and first-draft output is insufficient.
---

You are a writing coach using a structured draft-evaluate-revise process.

---

## Stage 1 — Write the first draft

Write a {{WORD_COUNT}}-word essay on the following topic.

**Topic:** {{ESSAY_TOPIC}}
**Audience:** {{AUDIENCE}}
**Purpose:** {{PURPOSE}}

[First draft here]

---

## Stage 2 — Evaluate against criteria

Score the draft 1-5 on each criterion. For each criterion scoring 3 or below,
write one specific sentence describing what to fix.

| Criterion | Score (1-5) | Required fix (if ≤ 3) |
|-----------|------------|----------------------|
| Clear thesis stated in intro | | |
| Each paragraph has one main idea | | |
| Claims are supported with evidence or examples | | |
| Transitions connect paragraphs logically | | |
| Conclusion synthesizes (doesn't just restate) | | |
| Tone matches audience | | |
| No sentence is longer than 35 words | | |

**Overall score:** ___ / 35
**Critical fixes required (score ≤ 3):** ___

---

## Stage 3 — Revise

Rewrite the essay, addressing every required fix identified in Stage 2.
Do not change sections that scored 4-5 unless fixing a required fix requires it.

After the revision, list what changed in bullet points:
- Changed: ...
- Changed: ...

**Revised draft:**

---

## Why this technique

Reflexion prevents the model from "anchoring" on the first draft during revision. By scoring each criterion before revising, the model generates an objective external critique that it then acts on — rather than producing a revision that feels different but has the same structural flaws.

## When to escalate

If the essay still scores below 25/35 after one revision → run a second Reflexion cycle (Stage 2→3 only on the revised draft). If the content accuracy is uncertain → insert a Generate-Knowledge (Technique 8) step before Stage 1 to prime factual content.
