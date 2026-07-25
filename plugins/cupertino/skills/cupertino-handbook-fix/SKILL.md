---
name: cupertino-handbook-fix
description: Applies exactly the eligible mechanical:true findings from cupertino-handbook-check's handbook_check_<domain>_summary.json -- single-location, unambiguous handbook-rule fixes -- via the handbook-remediator agent, then immediately checks every fix with a fresh, independent handbook-verifier agent that is blind to the remediator's own rationale (never self-verifies, no exception even for trivial fixes). Use this only when the user explicitly wants to apply cupertino-handbook-check's findings, not just read them, and has set handbook.fix.mode to "fix" in .claude/cupertino.local.md. This is cupertino's only Edit-capable skill -- every other cupertino skill, including cupertino-handbook-check itself, is read-only. Do not use for findings with mechanical:false -- those are never auto-fixed by this or any cupertino skill.
---

Apply `cupertino-handbook-check`'s eligible `mechanical: true` findings,
clustered by file and rule (Step 1a) and dispatched to the
`handbook-remediator` agent once per cluster — the fourth and final
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

## Step 1a — Cluster by file and rule

Group the eligible-findings list from Step 1 into clusters, keyed by
`(file, ruleId)` — `file` is everything before the last `:<digits>` in
the finding's `evidence` string, `ruleId` is the finding's own `ruleId`
field. Findings that share both are the same handbook rule violated at
different lines in the same file — these become one cluster, dispatched
as a single `handbook-remediator` call in Step 3 and checked as a single
`handbook-verifier` call in Step 4. A finding that shares its `(file,
ruleId)` with nothing else is a singleton cluster of size 1. Never
cluster across files or across different rules, even when the fixes look
superficially similar.

For each cluster with more than one member, check whether the symbol-graph
built by `build_symbol_index.py` (resolve-or-build per
`references/parallel-safe-research-protocol.md`, same as this plugin's other
Workflow-tool skills) has an index for the cluster's file at
`symbol-graph/<file-slug>/_index.json`. Each finding's `evidence` gives a
`path:line`, never a resolved symbol name — read that one small index file
(sorted by line) and pick the nearest enclosing entry (the last one whose
`line` is `<=` the finding's line, or the closest overall if none qualifies),
then read that entry's own `symbol-graph/<file-slug>/<slug>.md` doc. If its
"Possibly related" section links to a same-file symbol whose location is
**not** already one of this cluster's cited locations, attach a
`possiblyRelated` note (the other symbol's name, kind, and line) to the
cluster for Step 3 to pass along. This never changes cluster membership or
blocks the dispatch — a missing, stale, or unbuilt symbol-graph/index is a
normal, expected outcome, not an error; proceed exactly as before when it's
absent.

## Step 2 — Dirty-tree gate

Run `git status --porcelain`. If it's not clean, **tell the user plainly**
that this step is about to edit tracked files and ask them to commit or
stash first, or explicitly confirm proceeding anyway — do not proceed
silently on a dirty tree. Checked once per invocation, before touching
anything.

## Step 3 — Dispatch `handbook-remediator`, once per cluster

Loop over the clusters from Step 1a within this one invocation. For each
cluster, dispatch the `handbook-remediator` agent
(`agentType: 'cupertino:handbook-remediator'`) exactly once, passing the
**entire cluster's** array of `{evidence, title, suggestedFix}` entries
— plus, when Step 1a attached one, a `possiblyRelated` note asking
`handbook-remediator` to `Read` that other location before editing and
return `blocked` for the affected cited location(s) if the rewrite would
actually touch or depend on it, rather than assuming independence from the
string-key match alone — never a dispatch spanning more than one cluster. The agent returns one
result per location (`{file, line, status, description, reason?}`, ...).
For each location that comes back `blocked`, report why verbatim; a
`blocked` location never blocks the rest of its cluster. Do not retry
with a broader prompt or a second guess at the fix.

## Step 4 — Dispatch `handbook-verifier`, blind, once per cluster

If every location in the cluster came back `blocked` in Step 3 (zero
`applied`), skip this step entirely for that cluster — there is nothing
to verify, and `handbook-verifier` must never be dispatched with an empty
locations array. Otherwise, immediately after each cluster
`handbook-remediator` returns — before moving to the next cluster —
dispatch `handbook-verifier`
(`agentType: 'cupertino:handbook-verifier'`) **once for the whole
cluster**, per the blind construction in
`references/handbook-verification.md`: pass **only** the shared handbook
rule text + its `detectionSignal`, and the array of **original, pre-fix**
`evidence`/`title` pairs from the locations in this cluster that
`handbook-remediator` reported as applied (not `blocked`) in Step 3 — do
**not** pass `handbook-remediator`'s own output (its
description of what it changed, its rationale, its confidence) for any
location, under any circumstance. `handbook-verifier` independently
judges and returns one verdict per location — it must never infer one
location's compliance from another's, even within the same cluster.

For each location whose verdict is `compliant: true`, report the fix as
accepted. For `compliant: false`, report the fix as **failed** — name the
file:line, the verifier's `reasoning`, and that a human should review it.
Never silently retry or self-override a `compliant: false` verdict for
any location.

Each finding gets its own accept/fail report — N findings fixed this run
means N separate reports, regardless of how many clusters they were
dispatched in, never one summary claiming the batch as a whole is "done."

Never commit or push, at any point in this skill.

## Present

Report: how many eligible findings were found, how many were fixed
(verifier-`compliant: true`) vs. `blocked` vs. verifier-rejected
(`compliant: false`), one line per finding. If Step 0 or Step 2 stopped
early, report that instead — clearly, as the actual outcome of this run,
not as an error to apologize for.
