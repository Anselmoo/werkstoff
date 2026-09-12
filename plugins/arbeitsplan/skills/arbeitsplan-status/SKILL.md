---
name: arbeitsplan-status
description: Read-only report on an arbeitsplan run that has already started — phases done, candidates built, referee verdicts, dispatch budget used, and whether a lock is open. Use when the user asks how the run is going, what the swarm decided, why something was denied, or what is still holding a lock. Advances nothing and writes nothing.
---

# Status

Reports what has already run. It has nothing to say outside its own pipeline, and it never
advances one.

## Steps

1. **Find the runs.** `analysis/arbeitsplan/*/workflow.json`. Report the most recent unless
   the user names one.
2. **Read the phase markers** under `.takt/<runId>/` — those are what takt gates on, so they
   are the authoritative record of which phases genuinely completed.
3. **Count the dispatch ledger** at `analysis/arbeitsplan/<runId>/dispatch/`. One file per
   distinct dispatch; the count against `budget.totalDispatches` is how much room is left.
4. **Report the lock.** If `run_scope.json` is open, say which phase it arms and how old it
   is. **Do not close it** — a stale lock denies every edit, which is the safe direction.
5. **Report candidate state** from the worktrees that still exist, and say plainly which were
   deleted as losers versus never built.

## Rules

- **Writes nothing, advances nothing, deletes nothing.**
- **Never infer a phase completed because its output looks present.** The marker is the
  record; a file can exist from a failed run. This repository has been burned exactly here —
  a failed run leaves the previous output in place.
- **Never re-open a lock or re-run a phase.** Report and stop.

## Output format

```
arbeitsplan status — ap-2026-09-12-a3f1  (compiled 41 min ago)
  problem   rate-limit the public search endpoint without changing its response shape
  backend   in-session
  budget    7 / 9 dispatches used

phases
  build     done      marker .takt/ap-2026-09-12-a3f1/built     3 candidates, 1 unmeasured
  referee   done      marker .takt/ap-2026-09-12-a3f1/refereed  1 accepted, 1 rejected
  land      NOT DONE  no marker

lock: OPEN on phase 'land', 6 min old
  While it is open every write outside the landing scope is denied. Release it only
  when you have decided the run is over:
      rm analysis/arbeitsplan/run_scope.json

worktrees
  c1  deleted (rejected)
  c2  .arbeitsplan/ap-2026-09-12-a3f1/c2   kept — this is the winner, not yet applied
  c3  .arbeitsplan/ap-2026-09-12-a3f1/c3   kept — unmeasured, useful for diagnosis

Next: arbeitsplan-run resumes at 'land'.
```

## Resources

- `references/workflow-spec-schema.md` — what the phases and markers in the report mean.
