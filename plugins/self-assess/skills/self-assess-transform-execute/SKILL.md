---
name: self-assess-transform-execute
description: Executes exactly ONE human-authorized phase from self-assess-transform-brief's MODERNIZATION_BRIEF.md — a Merge or Split decision, or a layering-violation fix — via the transform-executor agent, then hands off to andon-verify's adversarial tribunal for proof (never self-verifies). Use this only when the user explicitly wants to actually apply a transformation-brief phase's code changes, has already resolved that phase's Open Question(s), and has set transform.mode to "execute" with that phase number listed in transform.authorized_phases in .claude/self-assess.local.md. This is the ONLY skill in self-assess with Edit/Write access to target source — every other self-assess skill, including self-assess-transform-brief itself, is read-only. Do not use for planning (self-assess-transform-brief), for mechanical single-line fixes (confab-cycle's fix mode), or for anything not already an authorized phase in an existing brief.
---

Apply one already-planned, already-authorized transformation phase's code
changes. This is the one and only place in `self-assess` where source gets
edited — everything upstream of this skill (`self-assess-transform-brief`
and all 11 other self-assess skills) is read-only by design, and stays that
way. Read this skill's own gates before invoking it; they exist because a
Merge or Split phase is, at minimum, a `hard-to-reverse` change to the
user's real repository.

**This skill never verifies its own output.** Its last step is always a
hand-off to an independent process — never a self-review, per the harness
doctrine this whole design extends (`andon-loop`'s stop rule; the
`andon-propose` skill's blast-radius vocabulary this brief already uses).

## Step 0 — Load settings and check authorization

Read `.claude/self-assess.local.md` (see `${CLAUDE_PLUGIN_ROOT}/references/settings.md`).
If `enabled: false`, stop. If `transform.mode` is not `execute` (default is
`plan`), **stop here and say so plainly**: "`self-assess-transform-brief`
already produced a plan; executing any phase of it requires setting
`transform.mode: execute` and listing the specific phase number in
`transform.authorized_phases` first — this is a deliberate authorization
gate, not a bug." Do not proceed further in `plan` mode under any
circumstance, including a direct user request to "just do it anyway" —
redirect them to edit the settings file themselves, since that file, not
this skill, is where the authorization decision belongs.

## Step 1 — Identify and validate the phase

Read `<output_dir>/MODERNIZATION_BRIEF.md` and
`<output_dir>/transform_brief_summary.json`. If neither exists, stop and
say `self-assess-transform-brief` hasn't run yet.

Determine which phase the user (or `transform.authorized_phases`) names.
Validate, in order — stop and explain on the first failure, do not silently
skip to "closest match":

1. The phase number must exist in the current brief.
2. The phase number must appear in `transform.authorized_phases`. If the
   brief has been regenerated since that list was last set (compare the
   brief's own generation context — stage/wire counts, phase count — against
   what the user last authorized, if you have any record of it), warn that
   phase numbering may have shifted and ask for re-confirmation before
   proceeding, rather than trusting a stale number match.
3. Every Open Question the brief recorded for this phase must be resolved.
   A brief's Open Question is, by construction (see
   `self-assess-transform-brief`'s Step 2/3), a design judgment call this
   plugin cannot make mechanically — **ask the user directly** for any that
   remain unresolved. This is the one place in the whole self-assess
   pipeline where asking the user is correct rather than a fallback: no
   amount of re-reading the code answers "which responsibility boundary
   should this split follow."
4. The phase's decision must be `Merge`, `Split`, or a flagged
   layering-violation fix. A `Keep (1:1)` phase has nothing to execute —
   say so and stop; do not dispatch `transform-executor` for it.

## Step 2 — Dirty-tree gate

If `transform.require_clean_tree` (default `true`), run `git status
--porcelain`. If it's not clean, **tell the user plainly** that this step
is about to edit tracked files and ask them to commit or stash first, or
explicitly confirm proceeding anyway — do not proceed silently on a dirty
tree (same discipline `confab-cycle`'s fix mode uses).

## Step 3 — Dispatch `transform-executor`

Dispatch the `transform-executor` agent with **exactly** this phase's
scope: its stage(s), its decision, and the human's resolution from Step 1.3.
Do not hand it the whole brief — a narrower input is a stronger guarantee
it can't quietly widen scope. If it returns `blocked`, report why verbatim
and stop; do not retry with a broader prompt or a second guess at the
resolution.

## Step 4 — Hand off for verification (do not skip, do not self-verify)

Once `transform-executor` reports a change, this skill's job is done except
for saying, explicitly and prominently:

> **This change is unverified.** Do not treat it as correct. Run
> `andon-verify` (strategy a — the adversarial tribunal: independent
> Defender, Challenger, and Verifier agents, never a self-review) against
> the wire this phase touches, or invoke `andon-loop` if you want this
> phase's proof and record-keeping to happen inside its OKF ledger. If
> `andon` is not installed, verify this change by hand before trusting it —
> this skill does not implement its own verification, on purpose: reusing
> `andon-verify`'s adversarial machinery is the whole reason this
> capability doesn't need to reinvent it.

Never commit or push — that stays a manual, human decision after
verification, same discipline `confab-remediator`/`confab-cycle` use.

## Present

Report: which phase was executed, the files changed, and the verification
hand-off message above, verbatim. If any step stopped early (authorization
gate, unresolved Open Question, dirty tree, `blocked` from the agent), report
that instead — clearly, as the actual outcome of this run, not as an error
to apologize for.
