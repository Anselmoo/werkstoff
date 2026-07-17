---
name: compass-summarize-trace
description: This skill should be used after a compass-solve pipeline run has completed, when the user wants a compact, structured written record of what happened — for a handoff email, a PR/issue comment, a retrospective, or CLI documentation — rather than re-reading the full conversation transcript or the interactive reasoning-trace-viewer.html. Use when the user asks "summarize what we just did", "write this up for the team", "what happened in this pipeline run", or similar. Not for summarizing a single skill's output (just present that directly) — this skill is specifically for a completed compass-solve pipeline run with multiple phases to compress.
---

Compress a completed `compass-solve` pipeline run — Clarify, Explore (if
it ran), Decompose/Execute/Revise — into a compact, structured written
record, using data already present in the conversation (this skill never
re-fetches or re-runs anything; if the pipeline data isn't already in
context, there is nothing to summarize). Combines two mechanisms from
this plugin's own technique set:

- `compass-calibrate-format`'s few-shot anchoring
  (`../../references/knowledge/few-shot.md`): the 7-section structure
  below is non-obvious and prose alone under- or over-specifies it, so
  Step 2 anchors on 2-3 concrete worked examples rather than a bullet
  list of section names.
- `compass-draft-revise`'s score-then-selectively-revise mechanism
  (`../../references/knowledge/reflexion.md`): Step 3 scores the drafted
  summary against an explicit completeness criteria table (every stage
  mentioned, every decision justified) and revises only what scored
  at/below threshold, never a full rewrite.

See `../../references/constraints.md` for the context-rot and
plausible-vs-verified constraints that apply across every `compass-*`
skill.

**Non-goal:** does not replace `assets/reasoning-trace-viewer.html` — use
that for visually exploring branch/stage structure interactively; use
this skill for a compact written record.

## Step 0 — Confirm the pipeline data is in context

This skill needs the actual results already produced by a completed
`compass-solve` run, present in the conversation from that skill's own
"Present" step — never re-run any phase to get them:

- The **Clarify** result: `scopedTask`, `knownFacts`,
  `flaggedUncertainties` (and how each blocking one was resolved, if
  `compass-verify-assumptions` ran on it).
- The **Explore** result, if that step ran: the branch table and the
  selected branch's name and rationale (and the
  `compass-negotiate-tradeoffs` hybrid, if that ran too).
- The Mode B result: `stages`, `waves`, `stageResults` (each stage's
  `modesUsed`, `output`, `notes`), `composedResult`, and `revised`
  (`scoreTable`, `revisedResult`, `changes`) — see
  `../../references/pipeline-cheatsheet.md` for the exact shape of each.

If any of this is missing (e.g. the user asks for a summary of a
pipeline run from a much earlier, now-compacted part of the
conversation), say so plainly rather than fabricating plausible-sounding
stage details — this skill summarizes what actually happened, not what
a pipeline run like this would typically produce.

## Step 1 — Draft the 7-section summary

Produce exactly these 7 sections, in this order:

1. **What was asked** — the original task, one sentence, not the full
   `scopedTask` restatement.
2. **What was assumed** — every `flaggedUncertainties` entry and how it
   was resolved: adopted under its default interpretation (non-blocking),
   resolved by `compass-verify-assumptions` (cite the outcome), or
   answered by the user directly (blocking).
3. **Approaches weighed** — *omit this section entirely if Explore did
   not run.* If it ran: the branch table (name, Feasibility/Impact/Risk/
   Total), the selected branch and its rationale, and the hybrid's
   verdict if `compass-negotiate-tradeoffs` ran.
4. **What ran and in what order** — a table: `wave | stage | modes used
   | status`, one row per stage from `dag.stages`, ordered by `wave`.
5. **What was produced** — one to two sentences per leaf stage (a stage
   no other stage depends on — see `stats.leafStageCount`), summarizing
   its `output`, not reproducing it verbatim.
6. **What was revised** — the `revised.scoreTable`'s criteria that
   scored at or below `compass-draft-revise`'s threshold, and the
   `revised.changes` bullets. If nothing was revised, say so plainly
   rather than omitting the section.
7. **What was NOT done** — explicit non-goals from the Clarify/Explore
   phases: branches proposed but not selected (name + one-line reason),
   any `flaggedUncertainties` that stayed unresolved and were assumed
   rather than settled.

## Step 2 — Anchor the section shape on worked examples

Before finalizing the draft, check it against these two worked examples
of the expected density and tone — not templates to fill in verbatim,
but calibration for how compressed each section should be:

<examples>
<example>
<input>A compass-solve run that skipped Explore (one obvious approach),
decomposed into 3 sequential stages, and needed one revision cycle.</input>
<output>
**What was asked:** Add rate limiting to the public API's `/search`
endpoint.

**What was assumed:** "Rate limit" defaulted to per-IP token bucket
(confidence 65, flagged non-blocking) — no other reading would have
changed the deliverable, so this proceeded without a pause.

**What ran and in what order:**
| Wave | Stage | Modes used | Status |
|---|---|---|---|
| 0 | design-limiter | none | done |
| 1 | implement-limiter | compass-ground-evidence | done |
| 2 | add-tests | none | done |

**What was produced:** `add-tests` (the sole leaf stage) delivered a
token-bucket middleware with 6 test cases covering the limit boundary
and a burst-then-cooldown scenario.

**What was revised:** 1 criterion scored 2/5 ("error response includes
a Retry-After header") — fixed by adding the header to the 429 response
path.

**What was NOT done:** No alternative rate-limiting strategy (sliding
window, distributed store) was evaluated — Explore was skipped since
only one approach was reasonable for this scope.
</output>
</example>
<example>
<input>A compass-solve run where Explore ran with 3 branches, a close
runner-up, and no revision was needed.</input>
<output>
**What was asked:** Decide how to migrate the legacy auth service.

**What was assumed:** "Migrate" meant a live cutover, not a parallel-run
deprecation window (confidence 55, flagged, resolved by
`compass-verify-assumptions` citing the ticket's SLA language — 92
confidence after).

**Approaches weighed:** 3 branches — "Strangler fig" (total 24, winner),
"Big-bang rewrite" (total 21), "Parallel-run with feature flag" (total
23, close runner-up). Strangler fig won on lower risk despite a tied
total with the parallel-run branch.

**What ran and in what order:** [stage table, 4 stages, 2 waves]

**What was produced:** [1-2 sentences per leaf stage]

**What was revised:** Nothing scored at or below threshold — reported
as-is, no revision cycle ran.

**What was NOT done:** "Big-bang rewrite" was not pursued (highest risk
score, no incremental rollback path). "Parallel-run" was not pursued
despite its close score — its blocker (dual-write consistency) was
judged harder to de-risk than strangler fig's.
</output>
</example>
</examples>

## Step 3 — Score for completeness, revise only what's missing

Score the draft against this criteria table (1-5, threshold 3 —
`compass-draft-revise`'s default):

| Criterion | Score (1-5) | Required fix (if ≤3) |
|---|---|---|
| Every stage in `dag.stages` appears in the "What ran" table | | |
| Every `flaggedUncertainties` entry is accounted for in "What was assumed" | | |
| Every leaf stage's output is summarized in "What was produced" | | |
| "What was revised" is present even when nothing was revised (states so explicitly) | | |
| "Approaches weighed" is omitted (not left empty) when Explore didn't run | | |
| Every rejected branch/approach has a stated reason in "What was NOT done" | | |

Revise only the criteria that scored at or below 3, per
`compass-draft-revise`'s own discipline — do not regenerate sections that
already passed. Report the score table and the revision list (or state
plainly that nothing needed revision) alongside the final summary.

## Relationship to other compass skills

Reads the outputs of every other phase in the `compass-solve` pipeline
but produces none of them itself — this skill runs strictly after a
pipeline completes, never interleaved with it. Distinct from
`assets/reasoning-trace-viewer.html`: that renders the same `dag`
interactively for visual exploration; this skill produces a compact
written record for contexts where a browser isn't the right medium
(handoff email, PR comment, CLI-only environment).
