---
name: self-assess-idiom-fix
description: Applies exactly the eligible "modernization"-category findings from self-assess-code-idiom's code_idiom_summary.json -- mechanical, single-location deprecated-idiom rewrites (e.g. Optional[X] to X | None) -- via the idiom-remediator agent, then hands every fix off to andon-verify's adversarial tribunal for proof (never self-verifies, no exception even for trivial rewrites). Use this only when the user explicitly wants to apply code-idiom's modernization findings, not just read them, and has set idiom_fix.mode to "fix" in .claude/self-assess.local.md. This is one of only two skills in self-assess with Edit access to target source (the other is self-assess-transform-execute) -- every other self-assess skill, including self-assess-code-idiom itself, is read-only. Do not use for "smell"-category findings (those are never auto-fixed by this or any self-assess skill), for architectural Merge/Split changes (self-assess-transform-execute), or for house-rules violations (self-assess-lint-audit has no auto-fix path).
---

Apply `self-assess-code-idiom`'s eligible `modernization` findings, one at
a time, via the `idiom-remediator` agent — one of only two Edit-capable
paths in `self-assess` (the other is `self-assess-transform-execute`).
`self-assess-code-idiom` itself remains unconditionally read-only; this
skill is the separate, explicitly-gated place where a subset of its
findings can actually be applied.

**This skill never verifies its own output.** Its last step, for every
fix, is always a hand-off to an independent process — never a
self-review. This applies with zero exceptions, even to the most
mechanical single-line rewrite, per this plugin's deliberate choice to
prioritize one consistent safety story over proportionality to blast
radius.

## Step 0 — Load settings and check authorization

Read `.claude/self-assess.local.md` (see
`${CLAUDE_PLUGIN_ROOT}/references/settings.md`). If `enabled: false`,
stop. If `idiom_fix.mode` is not `fix` (default `propose`), **stop here
and say so plainly**: "`self-assess-code-idiom` already reports
modernization findings; applying any of them requires setting
`idiom_fix.mode: fix` first — this is a deliberate authorization gate,
not a bug." Do not proceed in `propose` mode under any circumstance,
including a direct request to "just do it anyway" — redirect the user to
the settings file.

## Step 1 — Build the eligible-findings list

Read `<output_dir>/code_idiom_summary.json`. If it doesn't exist, stop
and say `self-assess-code-idiom` hasn't run yet.

Filter its `findings[]` array to entries where **both** hold:
- `category === "modernization"` (never `"smell"` — permanently out of
  scope; fixing a smell requires design judgment a mechanical rewrite
  can't supply).
- No `severityNote` field present (its presence means
  `self-assess-code-idiom`'s own Verify phase already flagged this
  finding as a split/uncertain verdict — this skill never second-guesses
  that by attempting a fix anyway).

This is the **eligible-findings list** for the run. **Zero eligible
findings is a valid, expected outcome, not an error path** — a
fully-migrated codebase genuinely has nothing to fix here. Report "0
eligible findings — nothing to do" plainly and stop; never lower the
filter criteria or otherwise manufacture a finding to justify the run.

## Step 2 — Dirty-tree gate

Run `git status --porcelain`. If it's not clean, **tell the user
plainly** that this step is about to edit tracked files and ask them to
commit or stash first, or explicitly confirm proceeding anyway — do not
proceed silently on a dirty tree (same discipline
`self-assess-transform-execute` and `confab-cycle`'s fix mode use).
Checked once per invocation, before touching anything.

## Step 3 — Dispatch `idiom-remediator`, once per eligible finding

Loop over the **entire eligible-findings list** from Step 1 within this
one invocation. For each finding, dispatch the `idiom-remediator` agent
(`agentType: 'self-assess:idiom-remediator'`) with **only** that one
finding's `evidence` (file:line), `description`, and `suggestedFix` —
never a batch covering multiple findings ("one dispatch, one report"
means one `idiom-remediator` call per finding, not one skill invocation
per finding). If it returns `blocked`, report why verbatim and move to
the next finding in the list — do not retry with a broader prompt or a
second guess at the fix.

## Step 4 — Hand off for verification (do not skip, do not self-verify)

Immediately after each fix `idiom-remediator` applies — before moving to
the next finding in the loop — report explicitly:

> **This change is unverified.** Do not treat it as correct. Run
> `andon-verify` (strategy a — the adversarial tribunal: independent
> Defender, Challenger, and Verifier agents, never a self-review) against
> this fix, or invoke `andon-loop` if you want this and future fixes
> proven and recorded inside its OKF ledger. If `andon` is not installed,
> verify this change by hand before trusting it — this skill does not
> implement its own verification, on purpose.

Each fix gets its own hand-off message — N findings fixed this run means
N separate hand-offs, never one summary claiming the batch as a whole is
"done."

Never commit or push, at any point in this skill.

## Present

Report: how many eligible findings were found, how many were fixed vs.
`blocked`, and the verification hand-off message above, once per fix,
verbatim. If Step 0 or Step 2 stopped early, report that instead —
clearly, as the actual outcome of this run, not as an error to apologize
for.
