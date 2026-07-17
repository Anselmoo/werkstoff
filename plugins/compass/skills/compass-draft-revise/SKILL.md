---
name: compass-draft-revise
description: Scores an already-drafted artifact against an explicit, numbered criteria table (1-5 per criterion) and revises only the criteria that land at or below a stated threshold, then reports exactly what changed. Use this when a document, prompt, code comment, plan section, or any other drafted artifact needs a second pass against known success criteria rather than a vague "make it better" rewrite, when the artifact already has explicit criteria to check (e.g. from a scoped problem statement) or criteria need to be elicited before scoring can start, or when the user asks to "revise this draft", "score this against criteria", "iterate on what I wrote", or "apply reflexion" to an existing artifact.
---

Iterate a drafted artifact against its own explicit, stated criteria — never
vibes. Built on `reflexion.prompt.md`'s exact
draft → score-against-numbered-criteria → revise-only-what-scored-low →
list-what-changed structure, generalized from essays to any artifact. The
discipline this skill exists to enforce: **revising is not rewriting.** A
full rewrite that "feels different" but repeats the same structural flaws
is not what this skill produces; a surgical fix to exactly the rows that
scored low, with everything else left untouched, is.

This skill assumes the artifact is already drafted. If nothing has been
written yet, draft it first (using whatever compass skill or plain
judgment the task calls for) and then invoke this skill on the result —
do not fold first-draft generation into this skill's own steps.

## Step 1 — Get the criteria table

Criteria must be explicit and numbered before any scoring happens; never
score against an implicit sense of "good."

Check first whether `compass-clarify-scope` has already run in this
conversation and produced a scoped problem statement. If it has, look for
a `success_criteria` field (or whatever the shape of that skill's actual
finished output calls it — `compass-clarify-scope`'s `SKILL.md` is the
source of truth for the exact field name; do not assume this name is
final if that skill's output has changed since this was written) and use
those criteria verbatim as the table's rows, adapting only their phrasing
into single, checkable properties (see below). `compass-clarify-scope`
allows individual `success_criteria` entries to carry
`status: missing — needs elicitation` rather than a stated or inferred
criterion — for any entry in that state, do not silently drop it or
treat the whole list as usable: elicit that one criterion fresh (same
as the no-scoped-problem case below) while still reusing the other,
already-stated entries verbatim. A partially-usable list is not the
same as an absent one.

If no scoped problem statement is available, elicit criteria fresh:
ask what "good" means for this specific artifact, and push for 3-7
concrete, checkable properties — each one a single verifiable claim
someone could score without guessing the drafter's intent, not a vague
axis like "quality" or "clarity." Mirror the template's own criteria
style:

| Criterion | Score (1-5) | Required fix (if ≤ threshold) |
|---|---|---|
| Clear thesis stated in intro | | |
| Each claim is supported with evidence or a citation | | |
| Tone matches the stated audience | | |

State the revision threshold explicitly before scoring — default **3**
on the 1-5 scale (matching the template), or `.claude/compass.local.md`'s
`revision_threshold` if that file exists and sets it, i.e. anything
scoring at or below the threshold gets revised, everything above is left
alone. Raise the threshold (e.g. to 4) for higher-stakes artifacts if the
user says so; state whichever threshold is actually in force in the
output so it's never left implicit.

## Step 2 — Score the draft

Score the draft 1-5 against every row in the table, independently of how
polished the draft "feels" overall — a fluent draft can still score low
on a specific, narrow criterion (e.g. missing a citation), and a rough
draft can score high on a narrow one (e.g. correct thesis placement).
For every criterion at or below the threshold, write one specific
sentence in the "Required fix" column describing exactly what to change —
not "improve this," a concrete, actionable fix. Report the overall score
(sum, or average) and the count of criteria at or below threshold before
moving to Step 3.

## Step 3 — Revise only what's at or below the threshold

Revise the draft, addressing every required fix from Step 2. Do not
touch sections or passages tied only to criteria that scored above the
threshold — the anchoring problem Reflexion exists to prevent is a model
treating "revise" as license to regenerate everything, which produces a
draft that reads differently but keeps the same structural flaws (or
introduces new ones) in the parts that were already fine. If fixing a
required fix genuinely requires touching a passage that also serves an
above-threshold criterion (e.g. rewording a sentence to add a missing
citation necessarily touches its clause structure), that's allowed — the
constraint is "revise only what the fixes require," not "revise
character-for-character single lines."

## Step 4 — Report what changed

After the revision, list what changed in bullet points, one bullet per
required fix from Step 2, e.g.:

- Changed: added a source citation to the claim in paragraph 3
  (criterion: "each claim is supported with evidence").
- Changed: reordered the intro's second sentence to state the thesis
  explicitly (criterion: "clear thesis stated in intro").

Never present a revision without this list — the list is what proves the
revision addressed the score, not a coincidental side effect of a
broader rewrite. If nothing scored at or below the threshold, say so
plainly and skip revision entirely: report the score table and stop.

## Escalation — second cycle

If the artifact still scores at or below the threshold on any criterion
after one revision, run a second cycle: repeat Step 2 (score) then
Step 3 (revise) on the revised draft only — do not re-run Step 1's
criteria elicitation, the criteria table doesn't change between cycles.
Matches the template's own escalation rule (a fixed criteria bar, unmet
after one pass, gets a second pass rather than a different technique).

## Relationship to other compass skills

Not `compass-optimize-instruction`: that skill generates and scores
*multiple candidate* instructions for a *recurring* task before picking
one (APE); this skill iterates a *single, already-existing* artifact
against *its own* stated criteria (Reflexion). Not
`compass-clarify-scope`: that skill produces the criteria this skill
consumes when available, it does not itself score or revise anything.

Source technique (vendored locally, no external repo dependency):
`../../references/knowledge/reflexion.md` — see `../../references/knowledge/index.md`.

See `../../references/constraints.md` for the plausible-vs-verified and
context-rot constraints that apply to every criterion score and every
claimed fix in this skill's output.
