---
name: arbeitsplan-run
description: Executes a compiled workflow as a redundant swarm — N candidates over the same scope in their own git worktrees, judged blind, exactly one landed. Use after arbeitsplan-compile, or when the user asks to run the workflow, start the swarm, or build several versions and pick one. Halts and surfaces rather than retrying when candidates fail; convergence comes from widening, never from repeating. Writes only inside candidate worktrees until the landing step.
argument-hint: "[runId]"
---

# Run the swarm

N candidates build the **same scope** in isolation. Exactly one lands. The rest are deleted.

That is what makes a merge conflict impossible here: this is the same worktree isolation
`superpowers` uses, inverted. There, N worktrees do *different* work and must all be
reconciled — which is why `subagent-driven-development` forbids parallel implementers inside
one worktree "(conflicts)" and pushes the parallelism up to where the conflicts reappear.
Here, N worktrees do *the same* work and N−1 are discarded. Nothing is ever merged.

## Steps

1. **Read `workflow.json`.** Read the file; do not work from a summary of it. Refuse a
   `schemaVersion` you do not recognise rather than guessing at it.

2. **Open the run scope lock** before any dispatch:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/worktree_pool.py" open --spec analysis/arbeitsplan/<runId>/workflow.json --phase build
   ```

   This writes `analysis/arbeitsplan/run_scope.json`, which arms the guard. It is a
   **per-dispatch lock, not repo-level state** — that distinction is why this guard does not
   sweep up every other plugin's edits the way one in this repository once did.

3. **Create one worktree per candidate**, one angle each, from `workflow.json`'s `angles`.

4. **Dispatch the batch in ONE message.** Multiple dispatch calls in one response run in
   parallel; one per response is sequential. Each `arbeitsplan:candidate-builder` gets its
   angle, its worktree, the scope, and the acceptance list — and **never** another
   candidate's angle or output.

   With the Workflow tool available, `workflows/run.js` does this with the breaker in code.
   Without it, dispatch the agents directly — the workflow is an optimisation, never the only
   path.

5. **Apply the breaker, per batch, never cumulatively.**

   - Exclude every `measured: false` candidate from the denominator. It is not a rejection;
     it is a candidate that was never fairly tried.
   - `measured == 0` → **acquisition problem.** The environment failed, not the contract. Fix
     the environment and re-run. Do not re-dispatch into a broken environment.
   - `accepted * 3 < measured * 2` → **contract problem.** Halt and say so: *the correct
     response is a better contract, not more agents.*

6. **Referee blind.** One `arbeitsplan:candidate-referee` per surviving candidate, each given
   the criteria and that candidate's diff only — never the builder's rationale, never another
   candidate. Landing is an **allowlist**: only `accepted`.

7. **Select by rule**, not by preference: most criteria met, then fewest files touched, then
   candidate id. If no candidate is `accepted`, **halt and surface**. All N failing the same
   way is a statement about the contract.

8. **Land exactly one diff.**

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/worktree_pool.py" open --spec ... --phase land
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/land_candidate.py" --run <runId> --candidate c2 --apply
   ```

   Optional gated synthesis, only if the spec opted in: one further writer, given the winner
   plus **explicitly named** elements to borrow. It must beat the plain winner on at least one
   declared criterion, or the plain winner lands unchanged.

9. **Delete the losers** — worktrees and branches — then close the lock and create the phase
   marker under `.takt/<runId>/`.

## Rules

- **Never re-dispatch an identical prompt.** The hook denies it, and the denial is correct:
  past the cap those rounds do not converge, they only cost. Widen instead — a new angle
  nobody tried — or stop.
- **Never let a builder write to the shared tree.** Only the landing step touches it.
- **Never treat an unmeasured candidate as a failure.** It has no rate, only missing data.
- **Never raise the budget mid-run.** That is a decision to re-compile.
- **Delegation nests at most 3 deep, and never in a cycle** — both enforced by the hook, see
  `references/delegation.md`. A dispatch to arbeitsplan's own agents is fan-out and is not
  counted; a dispatch to another plugin is.
- **A denial from another plugin's guard is that plugin doing its job.** Report it; never
  reach for its escape hatch.

## Output format

```
arbeitsplan run — ap-2026-09-12-a3f1, phase build
  c1  middleware-layer       measured   checks 3/3   diff 2 files
  c2  decorator-per-route    measured   checks 3/3   diff 2 files
  c3  reverse-proxy-config   UNMEASURED no nginx toolchain in the worktree

  breaker  accepted 2 / measured 2  (c3 excluded from the denominator) — pass

phase referee (blind)
  c1  rejected   a3 not met: requirements.txt gains 'slowapi'
  c2  accepted   3/3, evidence at src/api/search.py:41

phase land
  winner   c2 (3 criteria met, 2 files touched)
  applied  src/api/search.py, tests/test_ratelimit.py
  deleted  c1, c3 worktrees and branches — nothing merged
  marker   .takt/ap-2026-09-12-a3f1/landed

dispatches 7/9 budget.
```

A halt is an output, not a crash:

```
arbeitsplan run — ap-2026-09-12-a3f1 HALTED at phase referee
  accepted 0 / measured 3 — every candidate failed criterion a1 the same way.
  All three read the limit from a per-process dict, so a1 ("429 across workers")
  cannot be met inside the declared writeScope at all.
  This is a statement about the contract, not about the candidates.
  The correct response is a better contract, not more agents: re-compile with a
  scope that admits shared state, or drop a1.
  Nothing was landed. Worktrees kept at .arbeitsplan/ap-2026-09-12-a3f1/ for reading.
```

## Resources

- `references/candidate-contract.md` — what builders and referees exchange, and why the
  referee is starved.
- `references/delegation.md` — read before dispatching another plugin: the registry every
  plugin declares, the append-only ledger, and the depth cap plus cycle detection that bound
  how far a delegation may nest.
- `references/patterns.md` — the breaker's thresholds and the reason they are per-batch.
- `workflows/run.js` — the same fan-out with the breaker in code, when the Workflow tool is
  available.
