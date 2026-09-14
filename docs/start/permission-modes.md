# Permission modes, and which one werkstoff wants

A permission mode decides what Claude Code may do without asking. Pick the wrong one and
the session cannot do the work at all — every plan-mode cell in
[the measured examples](/examples/) produced an empty diff, because plan mode blocks edits
by design.

Cycle modes with `Shift+Tab`, or prefix one prompt with `/plan`.

## The modes

| mode | runs without asking | use it for |
|---|---|---|
| `default` (shown as **Manual**) | reads only | sensitive work, unfamiliar repos |
| `acceptEdits` | reads, file edits, common filesystem commands | editing code you are reviewing |
| `plan` | reads; edits blocked until you approve a plan | exploring before changing |
| `auto` | everything, with a classifier reviewing actions | long stretches you trust |
| `dontAsk` | pre-approved tools only; anything else is denied | CI and scripts |
| `bypassPermissions` | everything | isolated containers only |

Approving a plan offers exactly three answers: **Yes, and use auto mode**, **Yes, manually
approve edits**, and **No, keep planning**. `Shift+Tab` cycles `auto → default →
acceptEdits → plan → default`.

Auto mode needs a supported model (Opus 4.6+, Sonnet 4.6+, or a Fable model) and an
organisation that has not disabled it. `defaultMode: "auto"` does **not** take effect from
a project's `.claude/settings.json` — only user or managed settings set it.

## Which mode per workflow

| workflow | mode | evidence |
|---|---|---|
| Understand a repo | `plan` throughout — the work is read-only | [understand-repo](/examples/understand-repo) |
| Build a feature | `plan` to scope, then approve with "Yes, and use auto mode" | [build-feature](/examples/build-feature) |
| Fix a bug, harden | Manual or `acceptEdits` — **not** `plan` | [fix-bug](/examples/fix-bug) |
| Design a UI, review a plugin | `plan` until the brief is signed | [design-ui](/examples/design-ui), [review-plugin](/examples/review-plugin) |

**`acceptEdits` is the mode where work completes.** It is the only mode in the recorded
runs that produced real diffs: the `logsumexp` implementation and the `median` fix both
landed under it, while every `plan` cell ended with nothing written.

**`acceptEdits` is not "no more prompts", and the refusals are Bash-shaped.** Across four
recorded cells it refused 26 Bash calls — `cd` outside the working directory, `find` under
`~/.claude`, and compound commands whose second half needed approval. File edits went
through; shell commands are where it stops.

## What a hook does to all of this

A `PreToolUse` hook denial blocks in **every** mode, including `auto` and
`bypassPermissions`, and inside subagents. Nine werkstoff plugins register one. Choosing a
permissive mode does not buy passage past a plugin's own guard, and it is not supposed to.

The two refusals are reported differently, and the evidence pages keep them apart: a
**mode** refusal is the permission mode doing its job (`Cannot write to … while in plan
mode`), a **hook** refusal is a guard intervening.

## Plan mode and an open arbeitsplan run collide

While an `arbeitsplan` run-scope lock is open, a write to the plan-mode plan file at
`~/.claude/plans/…` is denied, because that path resolves outside the repository the run
was compiled against. Plan mode permits only that one file, so a subagent under both has
no legal move at all.

Recorded in `test/workflows/evidence/plan-file-under-lock.md` and reproducible in under a
second with `bash test/workflows/reproduce_hazard.sh`. Close the run, or plan outside it —
do not reach for either escape hatch to get past a guard that is working.

## Headless sessions

`claude -p` cannot approve a plan: `ExitPlanMode` is disabled there, in subagents as well.
A headless plan-mode run therefore measures the planning half of a workflow and nothing
after it. This is why the sweeps behind these pages record `plan` and `acceptEdits`
separately rather than treating plan mode as a prelude to execution.
