---
name: cupertino-review
description: >
  Runs a project through cupertino's full lifecycle pipeline — backwards ->
  focus -> [longevity & integrate, tension surfaced jointly] -> council ->
  prototype -> elevate -> unbox -> reveal -> [cannibalize, cadence-triggered,
  user-invoked only] — composing the plugin's other 10 skills as fixed stages
  instead of requiring the user to invoke them individually. Use when a
  project spans multiple lifecycle moments and the user wants the whole
  Steve-Jobs-grounded discipline applied end-to-end — "give this the full
  cupertino treatment", "review this project like Apple would", "run the
  whole design lifecycle on this", "apply cupertino start to finish", or a
  request that would otherwise mean chaining several cupertino-* skills by
  hand. Not for a single lifecycle moment with one obvious technique — use
  that one cupertino-* skill instead. cupertino-cannibalize never runs
  automatically as part of this pipeline.
---

The plugin's primary entry point: given a software project or feature
spanning multiple lifecycle moments, run it through the composed pipeline —
matching `compass-solve`'s "actual workflow, not a technique picker"
thesis. The 8 automatic stages below (`cupertino-cannibalize` is the
explicit 9th, non-automatic exception) are internal composition, not a
menu — the user never picks "now run the council"; they get a project
reviewed through the whole discipline, and the technique-grounded skills
are the mechanism underneath.

## When to use

- The task spans (or the user wants it to span) more than one lifecycle
  moment of a project — scoping, architecture, UI, build, ship — not a
  single isolated review.
- The user asks for "the full cupertino treatment," "review this like
  Apple would," or describes wanting the whole discipline applied, not one
  technique.
- You'd otherwise be manually chaining `cupertino-backwards` ->
  `cupertino-focus` -> ... -> `cupertino-reveal` by hand — this skill is
  exactly that chain, composed.

**Skip this skill** when exactly one lifecycle moment and one technique
apply — reach directly for that one `cupertino-*` skill instead. Running
the full 8-stage pipeline on a narrow single-technique request is the same
anchoring-on-process failure mode `compass-solve` warns against for its own
pipeline: techniques patch specific moments, they are not a default
posture for every request.

## Plain sequential logic — no Workflow tool

This is confirmed as **plain sequential skill logic** — no Workflow
machinery. Unlike `self-assess`/`confab`'s parallel-finder audits, and
unlike `compass-explore-branches`/`compass-optimize-instruction`'s genuine
parallel fan-out, every stage of this pipeline is a single-pass judgment
call applied to the same evolving project context, and most stages
(`cupertino-longevity` + `cupertino-integrate`, step 3) that could look
parallel are actually two views of the *same* decision that must be
presented jointly, not independently computed and merged — which is a
reason to keep this in-conversation rather than a reason to reach for
Workflow-based parallelism.

## The pipeline (fixed order, never reordered)

| Step | Stage | Skill(s) | Lifecycle moment |
|---|---|---|---|
| 1 | Backwards | `cupertino-backwards` | Before any architecture/design work starts |
| 2 | Focus | `cupertino-focus` | Scoping — portfolio/roadmap altitude |
| 3 | Longevity & Integrate | `cupertino-longevity` + `cupertino-integrate` (together, tension surfaced jointly) | Architecture-decision time |
| 4 | Council | `cupertino-council` | UI/frontend build-time |
| 5 | Prototype | `cupertino-prototype` | Build-time, parallel to Council |
| 6 | Elevate | `cupertino-elevate` | Build-time, applied to a commodity feature already in scope |
| 7 | Unbox | `cupertino-unbox` | Build/finishing-time |
| 8 | Reveal | `cupertino-reveal` | Ship-time |
| 9 | Cannibalize | `cupertino-cannibalize` | Post-ship, ongoing cadence — **cadence-triggered, user-invoked only, never automatic** |

## Optional handbook pre-flight

If a handbook artifact already exists under this project's configured
`handbook.output_dir` (see `references/handbook-settings.md`) for the
domain matching the work in scope — most often the `design` domain ahead
of Step 4 — consider running `cupertino-handbook-apply` for that domain
before Step 4 (Council) to load house-specific constraints into the brief.
This is optional enrichment, never a blocking dependency: it does not
change the 8-stage sequence above or its ordering, and this pipeline runs
identically whether or not a handbook exists.

## Step 1 — Backwards

Apply `cupertino-backwards`'s methodology directly (in-conversation
reasoning, no agent/workflow needed) to produce the one-sentence
customer-experience statement and the stated-request-vs-underlying-problem
split. This anchors every later step — if the project already has a
settled customer-experience statement from prior work, confirm it still
holds rather than skipping this step silently.

## Step 2 — Focus

Apply `cupertino-focus`'s methodology to the project's portfolio: enumerate,
grid, cut, and check the one-sentence test. If the project is a single
feature with no portfolio-level ambiguity (nothing to cut, nothing
sprawling), state that explicitly and move on rather than manufacturing a
grid where none is warranted.

## Step 3 — Longevity & Integrate (run together, present jointly)

Apply both `cupertino-longevity` and `cupertino-integrate` to the same
architecture decision(s) surfaced by Steps 1-2. This is the pipeline's one
mandatory joint step: **never present only one of the two readouts, and
never average them into a single verdict.** Report both explicitly
attributed ("longevity says X, integrate says Y") per both skills' own
TENSION RULE sections, then state the resolution actually chosen for this
decision and why.

## Step 4-5 — Council & Prototype (build-time, run alongside each other)

Apply `cupertino-council` to the UI/frontend surface and `cupertino-
prototype` to any load-bearing mechanism uncertainty from Step 3's
architecture decisions. These address different questions at the same
lifecycle moment — council governs how it looks and behaves, prototype
governs whether the mechanism underneath actually works. If Step 3
produced no open empirical questions worth spiking, note that and skip
Prototype's output for this pass rather than manufacturing a spike with
nothing genuine to test.

## Step 6 — Elevate

Apply `cupertino-elevate` only if a commodity feature is genuinely already
in scope for this build (see its own frontmatter: never seek one out
independently, never propose it as a new capability). If nothing in scope
qualifies, state that and skip — this step is opportunistic, not mandatory
on every pipeline run.

## Step 7 — Unbox

Apply `cupertino-unbox` to the project's first-run/onboarding/install
experience, once the build-time work (Steps 4-6) has produced something
worth a new user's first five minutes.

## Step 8 — Reveal

Apply `cupertino-reveal` at the finishing/ship-ready moment: exactly one
non-obvious, high-leverage addition, delivered in keynote-reveal structure
and actually built per its own Step 4.

## Step 9 — Cannibalize (never automatic)

`cupertino-cannibalize` is **not** part of this pipeline's automatic
execution. Do not run it as part of a `cupertino-review` invocation unless
the user has separately and explicitly asked for a cannibalization
analysis in the same request. If a `cupertino-review` run surfaces a
genuine "should we replace our own most successful thing" question
organically, name that observation in the Present step below and suggest
the user explicitly invoke `cupertino-cannibalize` — do not run it for
them.

## Present

Report, in this order:

1. **Customer experience** (Step 1) — the one-sentence statement, and the
   stated-request-vs-underlying-problem split if it surfaced a gap.
2. **Focus** (Step 2) — the cut list and one-sentence-per-survivor check,
   or "no portfolio-level ambiguity" if skipped.
3. **Architecture: Longevity & Integrate** (Step 3) — both readouts, side
   by side, plus the stated resolution.
4. **Council & Prototype** (Steps 4-5) — the council's Output Structure in
   full, plus the prototype's question/build/result/decision if one ran.
5. **Elevate** (Step 6) — the transfiguration output, or "not applicable
   this pass."
6. **Unbox** (Step 7) — the first-five-minutes redesign output.
7. **Reveal** (Step 8) — the one reveal, built.
8. **Cannibalize flag**, if Step 9 surfaced an organic candidate — named as
   a suggestion to separately invoke `cupertino-cannibalize`, never run
   automatically.

## Relationship to other cupertino skills

Every stage's methodology is owned by its corresponding skill's own
`SKILL.md` — this skill applies that methodology by following each one's
own process, it never reimplements it. Each of the 10 skills stays
independently invocable outside this pipeline for a narrower job: reach for
`cupertino-council` alone for a single UI review, `cupertino-longevity`
alone for a single architecture-fitness check (though its own frontmatter
still recommends pairing it with `cupertino-integrate` when the decision
has a real ownership dimension), `cupertino-reveal` alone for a single
ship-time addition, and so on — this skill exists for the case where a
project genuinely needs several stages, composed, not as the only
sanctioned entry point into the plugin.
