---
name: arbeitsplan-preflight
description: Read-only inventory of what a swarm run can and cannot do in this repository before any tokens are spent. Use before arbeitsplan-compile or arbeitsplan-run, when the user asks whether this repo is ready for a swarm, or when a run failed and the cause might be the environment rather than the work. Reports git/worktree support, test commands, other plugins' live guards, and any open run lock. Writes nothing.
---

# Preflight

Know what is on the bench before measuring it. A run that discovers mid-swarm that the repo
cannot make a worktree has already spent N dispatches on a result it cannot use.

## Steps

1. **Git and worktrees.** Is this a git repository? Can it create a worktree here — is the
   candidate directory ignored? A repo that cannot make worktrees can still use the matrix
   backend, so report the alternative rather than just failing.

2. **Acceptance checks.** What test command does this repo actually use? A run whose criteria
   carry no runnable check cannot be refereed, and that is better known now.

3. **Other plugins' live guards.** Report every guard that would see this run's edits — takt,
   cupertino, lehre, andon, confab, self-assess, nacharbeit — and its marker. A fix pass runs
   under them, and a denial from one is that plugin doing its job.

   **Never suggest another plugin's escape hatch.** Naming it as an inventory fact is
   reporting; recommending it is helping the user disable someone else's guard.

4. **Existing state.** Is `analysis/arbeitsplan/run_scope.json` open, and how old? Is
   `.claude/takt.local.md` present, and does it carry this plugin's provenance key?

5. **The matrix backend.** Is `claude` on PATH? Is `timeout` or `gtimeout` available (cells
   run untimed without one)? Is this session nested — because if so, the matrix runner will
   refuse, correctly, and the user must run it from a terminal.

6. **Say what the run can and cannot measure.** A missing checker means the phases that need
   it are listed as skipped, never silently passed. Name them.

## Rules

- **Writes nothing.** Not even a state directory.
- **Never infers a missing checker as present.** If there is no test command, say the
  acceptance criteria will have to be structural, and say what that costs.
- **Refuse to go further on an open lock.** Hand the user the release command. A stale lock
  denies every edit, which is the safe direction, and only a person decides to release it.

## Output format

```
arbeitsplan preflight — /Users/x/proj
  git                 yes (worktrees supported, .arbeitsplan/ is gitignored)
  test command        pytest -q            (from pyproject.toml)
  claude on PATH      yes
  timeout             gtimeout (coreutils)
  nested session      YES — the matrix runner will refuse; run it from a terminal

other guards live in this repository (a run executes under them; a denial from one is
reported, never bypassed):
  cupertino    marker .cupertino
  takt         marker .claude/takt.local.md  (no arbeitsplan provenance key — hand-written)

run lock: none open
state: workflow.json=absent, run_scope.json=absent, matrix results=absent

Can measure: every phase. Cannot measure: nothing skipped.
Caution: takt.local.md is hand-written. arbeitsplan-compile will REFUSE to overwrite it.
Next: arbeitsplan-compile to turn a problem into a spec.
```

## Resources

- `references/matrix-schema.md` — why a nested session cannot run the matrix.
- `references/workflow-spec-schema.md` — what compile will need from this repository.
