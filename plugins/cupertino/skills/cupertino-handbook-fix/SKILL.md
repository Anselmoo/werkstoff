---
name: cupertino-handbook-fix
description: Applies exactly the eligible mechanical:true findings from cupertino-handbook-check's handbook_check_<domain>_summary.json -- single-location, unambiguous handbook-rule fixes -- via the handbook-remediator agent, then immediately checks every fix with a fresh, independent handbook-verifier agent that is blind to the remediator's own rationale (never self-verifies, no exception even for trivial fixes). Use this only when the user explicitly wants to apply cupertino-handbook-check's findings, not just read them, and has set handbook.fix.mode to "fix" in .claude/cupertino.local.md. This is cupertino's only Edit-capable skill -- every other cupertino skill, including cupertino-handbook-check itself, is read-only. Do not use for findings with mechanical:false -- those are never auto-fixed by this or any cupertino skill.
---

Apply `cupertino-handbook-check`'s eligible `mechanical: true` findings,
one at a time, via the `handbook-remediator` agent — the fourth and final
stage of `cupertino`'s handbook lifecycle (`draft` → `apply` → `check` →
`fix`), and the plugin's only Edit-capable skill.
`cupertino-handbook-check` itself remains unconditionally read-only; this
skill is the separate, explicitly-gated place where a subset of its
findings can actually be applied.

**This skill never verifies its own output.** Its last action, for every
fix, is always a dispatch to a fresh, independent `handbook-verifier`
agent — never a self-review, and never a hand-off outside this plugin
(`self-assess-idiom-fix` hands off to `andon-verify`; `cupertino` cannot
assume `andon` is installed, so it internalizes the same discipline as a
self-contained blind adversarial pair). See
`${CLAUDE_PLUGIN_ROOT}/references/handbook-verification.md` for the full
protocol this skill and its two agents implement together.

Fully self-contained: this skill never invokes `self-assess` or `andon`
skills, agents, or workflows.

## Step 0 — Load settings and check authorization

Read `.claude/cupertino.local.md` (see
`${CLAUDE_PLUGIN_ROOT}/references/handbook-settings.md`). If `enabled:
false`, stop. If `handbook.fix.mode` is not `fix` (default `propose`),
**stop here and say so plainly**: "`cupertino-handbook-check` already
reports findings; applying any of them requires setting
`handbook.fix.mode: fix` first — this is a deliberate authorization gate,
not a bug." Do not proceed in `propose` mode under any circumstance,
including a direct request to "just do it anyway" — redirect the user to
the settings file.

Resolve `domain` per `${CLAUDE_PLUGIN_ROOT}/references/handbook.md`'s
domain-resolution table.

## Step 1 — Build the eligible-findings list

Read `<output_dir>/handbook_check_<domain>_summary.json`. If it doesn't
exist, stop and say `cupertino-handbook-check` hasn't run yet for this
domain.

Filter its `findings[]` array to entries where `mechanical === true`.
This is the **eligible-findings list** for the run. **Zero eligible
findings is a valid, expected outcome, not an error path** — a project
with no mechanical violations genuinely has nothing to fix here. Report
"0 eligible findings — nothing to do" plainly and stop; never lower the
filter criteria or otherwise manufacture a finding to justify the run.

## Step 2 — Dirty-tree gate

Run `git status --porcelain`. If it's not clean, **tell the user plainly**
that this step is about to edit tracked files and ask them to commit or
stash first, or explicitly confirm proceeding anyway — do not proceed
silently on a dirty tree. Checked once per invocation, before touching
anything.

## Step 3 — Dispatch `handbook-remediator`, once per eligible finding

Loop over the entire eligible-findings list from Step 1 within this one
invocation. For each finding, dispatch the `handbook-remediator` agent
(`agentType: 'cupertino:handbook-remediator'`) with **only** that one
finding's `evidence` (file:line), `title`, and `suggestedFix` — never a
batch covering multiple findings. If it returns `blocked`, report why
verbatim and move to the next finding in the list — do not retry with a
broader prompt or a second guess at the fix.

## Step 4 — Dispatch `handbook-verifier`, blind, immediately after each fix

Immediately after each fix `handbook-remediator` applies — before moving
to the next finding in the loop — dispatch `handbook-verifier`
(`agentType: 'cupertino:handbook-verifier'`) per the blind construction in
`references/handbook-verification.md`: pass **only** the handbook rule
text + its `detectionSignal` (read from the handbook artifact) and the
**original, pre-fix** `evidence`/`title` from the Step 1 finding — do
**not** pass `handbook-remediator`'s own output (its description of what
it changed, its rationale, its confidence) to `handbook-verifier` under
any circumstance.

If `handbook-verifier` returns `compliant: true`, report the fix as
accepted. If it returns `compliant: false`, report the fix as **failed** —
name the file:line, the verifier's `reasoning`, and that a human should
review it. Never silently retry or self-override a `compliant: false`
verdict.

Each finding gets its own accept/fail report — N findings fixed this run
means N separate reports, never one summary claiming the batch as a whole
is "done."

Never commit or push, at any point in this skill.

## Present

Report: how many eligible findings were found, how many were fixed
(verifier-`compliant: true`) vs. `blocked` vs. verifier-rejected
(`compliant: false`), one line per finding. If Step 0 or Step 2 stopped
early, report that instead — clearly, as the actual outcome of this run,
not as an error to apologize for.
