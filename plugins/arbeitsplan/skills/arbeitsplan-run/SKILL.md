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
   `schemaVersion` other than `"2"` rather than guessing at it. Then branch on
   `backend.kind` — it is a decision the spec already made, never yours to re-make:
   `workflow` → follow [The workflow backend](#the-workflow-backend) below; `matrix` →
   `arbeitsplan-matrix`; `in-session` → the steps here.

   A phase with `mode: "plan"` never runs under the lock: `worktree_pool.py open` refuses it,
   because plan mode plus an open lock leaves no legal write. Close, run that phase in plan
   mode, then open the next one.

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

   These are in-session dispatches, so the guard sees each one. The workflow backend is a
   different run, compiled for it — never switch to it mid-run.

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

9. **Delete the losers** — worktrees and branches — then record the phase as closed and close
   the lock:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/record_event.py" phase --run <runId> --phase land --status closed
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/worktree_pool.py" close
   ```

   `close` **refuses** a phase that recorded no terminal event. On a halt, close with
   `--halt "<the specific reason>"`: a halt is an event in `run.jsonl`, never an absence.

## Referee-owned artifacts (#77)

If `workflow.json` declares `refereeOwned`, its `referee-fixture` phase runs first, exactly
like any other phase (open the lock, dispatch its `agentType`, record the output, close). Once
it has written those paths, baseline them **once**:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/referee_owned.py" record --run <runId>
```

A second `record` for the same run is refused: the baseline is taken at creation, never
re-taken to accommodate a later change. `worktree_pool.py open` already narrows a fan-out
phase's lock to exclude every `refereeOwned` path, so the guard denies a candidate's Edit/Write
before it lands — but that covers only the tool calls the guard's matcher sees. Re-verify
before landing (step 8), as the belt to that guard's suspenders:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/referee_owned.py" verify --run <runId>
```

`land_candidate.py` independently refuses (citing `refereeOwned` by name) any candidate diff
that touches one of these paths, so the same rule is checked three ways: at the lock, at
landing, and by content.

## Stacked fan-outs across waves (#79)

A later wave's builders should sometimes start from an **earlier wave's refereed winner**,
not from HEAD — that is what a `fanout-redundant` phase's `base: "<phaseId>"` declares. Once a
phase's candidate is selected (step 7 above) and would normally just land (step 8), promote it
instead if a later phase names it as `base`:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/worktree_pool.py" promote --run <runId> --phase build-w1 --candidate c2
```

This commits everything sitting in that candidate's worktree — untracked files included — and
points `arbeitsplan/<runId>/base/build-w1` at the new commit. The next wave's `create` then
reads it automatically:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/worktree_pool.py" create --spec analysis/arbeitsplan/<runId>/workflow.json --phase build-w2 --count 2
```

If `build-w2` declares `base: "build-w1"`, every worktree this creates starts from the promoted
branch instead of HEAD; if `build-w1` was never promoted, `create` **refuses**, naming the
missing branch, and creates nothing. A `--phase` whose phase carries no `base` (or `create` with
no `--phase` at all) behaves exactly as before: from HEAD.

Base branches deliberately **survive** an ordinary `worktree_pool.py destroy --run <runId>` — a
still-pending later wave may need to stack on one. Only pass `--bases` once the whole run is
actually done with them:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/worktree_pool.py" destroy --run <runId> --bases
```

`compile_spec.py --strict` is the check that a stacked run actually declared every `base` it
needed: a `fanout-redundant` phase whose transitive `requires` reach another `fanout-redundant`
phase with no `base` chain reaching it back prints `WARNING ... [AP-SIBLING-INVISIBLE] ...`
naming both phases. A plain compile still writes past a warning (exit 0); `--strict` treats one
as a rejection (exit 1) — run compilation with `--strict` before dispatching a stacked run.

## The workflow backend

When `backend.kind` is `"workflow"`, the whole phase graph runs inside `workflows/run.js`,
and this session does only the three things the Workflow tool cannot: read files, run
plan-mode phases, and land.

1. **Launch it with the spec as data.** The Workflow tool has no filesystem, so pass the
   parsed `workflow.json` verbatim: `args: {spec}` (plus `startAt` and `carry` on a resume).
   No run-scope lock is open while it runs — nothing inside writes the shared tree.
2. **Persist what it returns, before reading it.** Every return carries `events`:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/record_event.py" workflow --run <runId> --result result.json
   ```

   A halt is an event. Record it even — especially — when the run aborted.
3. **On `pending_plan_node`, run that phase here, in plan mode**, by dispatching its
   `agentType` with the carried data. Record its output, add it to `carry` under the phase id
   (`carry.contract.acceptance` replaces the compiled acceptance for later phases), and
   relaunch with `startAt: <resumeWith>`. Loop state lives here, never in the script.
   That same command writes `candidates/<id>.json` and `referee/<id>.json` for every
   candidate the return carries, once each, never overwriting.
3b. **Record a plan-mode phase's output** the same way:
   `record_event.py phase-output --run <runId> --phase <id> --output <file>`. An adjudicator's
   `verdict: "land"` is what gives a borrowed synthesis its referee record; without it,
   `land_candidate.py` refuses the synthesis like any unjudged candidate.
4. **On completion, land in-session.** `worktree_pool.py open --phase <last>` and
   `land_candidate.py`, where the hook and the `writeScope` check both run. The workflow never
   lands. `land_candidate.py` writes `landed.json`, with `divergedFrom` if what landed differs
   from the recorded candidate.

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
- `workflows/run.js` — the workflow backend: executes `spec.phases`, halts before each
  plan-mode phase, counts the dispatch budget in code, and returns span-shaped `events`.
- `references/backend-selection.md` — why a run was compiled for the backend it names.
