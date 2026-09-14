# Measured: plan mode cannot coexist with an open arbeitsplan run-scope lock

**Reproduce it yourself:** `bash test/workflows/reproduce_hazard.sh` — no tokens, no agents,
no network. It feeds arbeitsplan's `PreToolUse` guard the exact payload Claude Code sends,
with the `plan-under-lock` fixture as the working directory.

Recorded 2026-09-14 against `plugins/arbeitsplan/hooks/arbeitsplan_guard.py`.

## What was measured

**Probe 1 — the plan-mode plan file.** Plan mode permits writing exactly one file, the plan at
`~/.claude/plans/<name>.md`. With a run-scope lock open, that write is denied, `exit=2`:

> arbeitsplan: '../../../../../../../../../../.claude/plans/example-plan.md' resolves to
> '/Users/…/.claude/plans/example-plan.md', outside the repository at '…/plan-under-lock'.
> A run's writes stay inside the tree it was compiled against. Set `ARBEITSPLAN_DISABLE_GUARD=1`
> to bypass this guard, or close the run (remove `analysis/arbeitsplan/run_scope.json`) …

**Probe 2 — an in-scope path during a fan-out.** A write to `pipeline/score.py`, which the
lock's own `writeScope` names, is also denied, `exit=2`, for a different reason:

> arbeitsplan: 'pipeline/score.py' is a write to the shared tree while fan-out phase 'build'
> (fanout-redundant) is in flight. During a fan-out every candidate writes only inside its own
> worktree, and exactly one diff is applied afterwards …

## Why it matters

A subagent running under plan mode **and** an open run-scope lock has no legal move: plan mode
allows only the plan file, and the guard denies exactly that path. Neither component is wrong on
its own. Observed first as three independent builder agents returning `measured: false` in run
`ap-2026-09-13-7c1f`, then reproduced deterministically here so the claim rests on a command
anyone can re-run rather than on an anecdote.

Neither denial is a malfunction, and neither escape hatch (`ARBEITSPLAN_DISABLE_GUARD=1`,
removing the lock) should be reached for to get past a guard that is doing its job. Close the
run, or do the planning outside it.
