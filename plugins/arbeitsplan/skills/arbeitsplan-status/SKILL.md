---
name: arbeitsplan-status
description: Read-only report on an arbeitsplan run that has already started — phases done, candidates built and refuted, referee verdicts, open doubts, halts with their reasons, dispatch budget used, whether a lock is open, and the single next command. Use when the user asks how the run is going, what the swarm decided, why it stopped, how to resume it, why something was denied, or what is still holding a lock. Advances nothing and writes nothing.
---

# Status

Reports what has already run. It has nothing to say outside its own pipeline, and it never
advances one.

## Steps

1. **Find the runs.** `analysis/arbeitsplan/*/workflow.json`. Report the most recent unless
   the user names one.
2. **Read the record, not the chat.** The run directory is the plan of record:
   `workflow.json` is the plan and never changes; `run.jsonl` is what happened. Ask the
   script, which derives everything from the log every time and stores no counter:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/record_event.py" status --run <runId>
   ```

   It reports closed and open phases, a halt with its reason, a pending plan-mode phase, a
   `FAILED-<stamp>.json` refusal, `complete.json`, counts per status (`refuted` candidates
   stay in the record after their worktrees are deleted; `doubt` entries carry
   `resolves_if`), and the **single next command**. Quote that command; do not compose your
   own. A run with no `run.jsonl` predates the record — say so, and fall back to the phase
   markers under `.takt/<runId>/`.
3. **Count the dispatch ledger** at `analysis/arbeitsplan/<runId>/dispatch/`. One file per
   distinct dispatch; the count against `budget.totalDispatches` is how much room is left.
4. **Report the lock.** If `run_scope.json` is open, say which phase it arms and how old it
   is. **Do not close it** — a stale lock denies every edit, which is the safe direction.
5. **Report candidate state** from the worktrees that still exist, and say plainly which were
   deleted as losers versus never built.

## Rules

- **Writes nothing, advances nothing, deletes nothing.**
- **Never infer a phase completed because its output looks present.** The record is the
  authority — a `closed` or `halted` event — and a file can exist from a failed run. This repository has been burned exactly here —
  a failed run leaves the previous output in place.
- **Never re-open a lock or re-run a phase.** Report and stop.

## Output format

```
arbeitsplan status — ap-2026-09-12-a3f1  (compiled 41 min ago)
  problem   rate-limit the public search endpoint without changing its response shape
  backend   in-session
  budget    7 / 9 dispatches used

phases (from run.jsonl)
  build     closed    3 candidates: 2 proposed, 1 unmeasured
  referee   closed    c2 accepted, c1 refuted (a3 not met)
  land      opened    no terminal event yet
  doubts    1  a3 transitive deps — resolves_if: pip-compile --dry-run shows no new package

lock: OPEN on phase 'land', 6 min old
  While it is open every write outside the landing scope is denied. Release it only
  when you have decided the run is over:
      rm analysis/arbeitsplan/run_scope.json

worktrees
  c1  deleted (rejected)
  c2  .arbeitsplan/ap-2026-09-12-a3f1/c2   kept — this is the winner, not yet applied
  c3  .arbeitsplan/ap-2026-09-12-a3f1/c3   kept — unmeasured, useful for diagnosis

next: phase 'land' is open: finish it, or record its halt with --status halted
```

## Resources

- `references/workflow-spec-schema.md` — what the phases and markers in the report mean.
- `scripts/record_event.py` — `status` derives the report from `run.jsonl`.
