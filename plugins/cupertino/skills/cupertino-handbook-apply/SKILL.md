---
name: cupertino-handbook-apply
description: Loads an existing design, code, testing, or documentation handbook for a project and produces concrete guidance/constraints for a specific upcoming task before work starts -- an active pre-flight consult, not passive background reading. Use before starting new work in a domain that already has a drafted handbook (see cupertino-handbook-draft) -- "about to build a settings screen, what does our design handbook say", "check the code handbook before I start the billing module", "what are our testing conventions before I write these tests". Stops and suggests cupertino-handbook-draft first if no handbook exists yet for the resolved domain -- this skill never drafts one itself. Independently invocable for any domain, and optionally consulted by cupertino-review before its Council stage when a design handbook already exists.
---

Load an existing handbook for one domain and turn it into concrete
constraints for the specific task about to start — a deliberate pre-flight
step, not something that happens automatically in the background. See
`${CLAUDE_PLUGIN_ROOT}/references/handbook.md` for the shared vocabulary and
domain-resolution rule every handbook-lifecycle skill uses.

Fully self-contained: never invokes `self-assess` or `andon` skills,
agents, or workflows.

## Step 0 — Load settings and resolve domain

Read `.claude/cupertino.local.md` if it exists (see
`${CLAUDE_PLUGIN_ROOT}/references/handbook-settings.md`). If `enabled:
false`, stop and say so. Note `handbook.output_dir` (default
`docs/cupertino/handbooks`).

Resolve `domain` per `${CLAUDE_PLUGIN_ROOT}/references/handbook.md`'s
domain-resolution table — from the task the user is about to start, not
from this skill's own name. If ambiguous, ask directly.

## Step 1 — Load the handbook

Read `<output_dir>/<domain>-handbook.md` and its
`<domain>-handbook_summary.json` sidecar. **If neither exists, stop here**
and say plainly: "No `<domain>` handbook found at `<output_dir>` — run
`cupertino-handbook-draft` for this domain first." This skill never drafts
a handbook on the fly; drafting and applying are separate, deliberate
steps with different authorization postures (draft only reads the
project, apply's whole purpose is to *constrain the work you're about to
do*, so it must be reading a human-reviewable artifact, not a
freshly-invented one from the same breath).

## Step 2 — Select the dimensions relevant to this task

Do not dump the whole handbook. From the description of the task about to
start, select only the dimensions whose `Rule` plausibly bears on it — a
task to "add a settings screen" pulls `component-states`, `layout-grid`,
`accessibility-baseline` from a design handbook, not `voice-microcopy`
unless the screen has user-facing copy too. For each selected dimension,
restate its `Rule` and `Enforcement` level as a direct constraint on the
upcoming task, in the task's own terms — not a copy-paste of the handbook
prose verbatim.

## Step 3 — Surface applicable exceptions

If the handbook's `## Exceptions & waivers` table has any entry whose
scope overlaps this task, state it explicitly alongside the constraint it
modifies — an absolute-sounding "must" that actually has a standing
exception for this area of the codebase needs to be presented as such, not
silently dropped or silently treated as still-absolute.

## Present

Report, as "before you start" guidance: the selected constraints (Rule +
Enforcement, one line each), any applicable exceptions, and a one-line
reminder that `cupertino-handbook-check` can verify compliance once the
work exists. If the user's request didn't name a concrete upcoming task
(e.g. they just asked "what does the handbook say"), report the handbook's
full dimension list instead of a filtered subset — the filtering in Step 2
only applies when there's an actual task to filter against.
