---
name: arbeitsplan-compile
description: Turns a stated problem into an executable, budgeted workflow spec plus the takt beats that enforce its order. Use when the user describes a change and wants it run as an agentic workflow, asks to plan or set up a swarm, says the advice they have is too vague to act on, or asks what shape a piece of work should be run in. Refuses and points at zirkel when the problem turns out to be a question rather than a change. Writes the run's workflow.json under analysis/arbeitsplan/ and, behind an approval gate, .claude/takt.local.md.
argument-hint: "<the problem, in a sentence or two>"
---

# Compile a problem into a workflow

Users are told to "use an agentic workflow" and don't, because the advice is too vague to
act on. This skill takes that transformation as its own job: in, a problem in prose; out, a
spec concrete enough that a machine runs it and a hook enforces it.

**The spec is a coded handoff, not a description.** This repository measured 9 of 11
skill-to-skill chains failing their handoff despite a schema existing upstream; the one that
worked copied its predecessor's JSON byte-for-byte into the next dispatch. So every later
phase *reads* `workflow.json`. Never paraphrase it into a prompt.

## Steps

1. **Read the schema first** — `references/workflow-spec-schema.md`. It is the authority on
   every key and on the rejections below.

2. **Decide the problem's shape.** A *change* alters files and can be checked. A *question*
   wants an answer.

   **A question is a refusal, not a smaller workflow.** Write an `out-of-scope-reasoning`
   record naming `zirkel:zirkel-solve`, write no phases, and stop. Compiling a swarm for a
   question produces three confident answers and no way to tell which is right.

3. **Scope it.** If the problem is vague, resolve it with the user before compiling — a spec
   compiled from a guess is precise about the wrong thing. When `zirkel` is installed,
   `zirkel:zirkel-clarify-scope` does this well; when it is not, ask directly and say that
   zirkel is not installed. Never fabricate zirkel-shaped output.

4. **Derive acceptance criteria.** Each is `{id, criterion, check}`, and `check` is `string |
   string[] | null` (#81): a single shell command, or a non-empty **array of shell commands**
   run independently, each exiting 0 on pass — a criterion with an array `check` passes only
   when every element does. **At least one criterion must carry a real, runnable check.** A spec
   whose every criterion is prose is a spec nothing can referee. Any other shape (a number, an
   object, an empty string, an empty list, or a list with a non-string element) is rejected as
   `AP-CHECK-SHAPE`.

5. **Get the write scope.** Dispatch `arbeitsplan:scope-prover`. An empty or underivable
   scope is a rejection — never read an absent scope as "anything".

6. **Choose patterns.** Dispatch `arbeitsplan:pattern-researcher`, or invoke
   `arbeitsplan-patterns`. Every `phases[].pattern` must be in the accepted list of
   `references/patterns.md`'s machine-readable index. An unknown id is rejected, never
   improvised.

   Give **every** phase `modelTier`, `mode` (`auto`, or `plan` for a planning phase) and
   `writes` (`worktree` for builders, `none` for referees and extractors, `shared` only for an
   in-session landing), plus a namespaced `agentType`. All four are required: an omitted
   value inherits the session's, and an inherited plan mode is how four builders became
   UNMEASURED in the run that added these keys.

7. **Choose the backend.** Invoke `arbeitsplan-backend`, which walks
   `references/backend-selection.md`'s table and returns `{kind, why[], acknowledgedGaps[]}`.
   Never write a bare string and never a free-text `why` — both are rejected.

8. **Set the budget.** `totalDispatches` must be at least the sum of every phase's `fanOut`.
   This is the ceiling the hook enforces; the run cannot raise it, only a re-compile can.

9. **Write the spec.**

   ```bash
   python3 -B "${CLAUDE_PLUGIN_ROOT}/scripts/compile_spec.py" --out analysis/arbeitsplan --write
   ```

   It validates before writing and names the offending key on refusal.

10. **Emit the takt beats — behind an approval gate.**

   Ordering belongs to `takt`, not to this plugin's hook. But writing `.claude/takt.local.md`
   makes takt **live and fail-closed** in this repository, so it is the user's decision, not
   yours. Show the beats, say plainly that takt will begin denying out-of-order calls, and
   write only on a yes.

   ```bash
   python3 -B "${CLAUDE_PLUGIN_ROOT}/scripts/emit_beats.py" analysis/arbeitsplan/<runId>/workflow.json --write
   python3 plugins/takt/scripts/validate_beats.py .claude/takt.local.md
   ```

   If `.claude/takt.local.md` already exists without this plugin's provenance key, **refuse
   and surface it.** takt reads only the first fenced block, so merging is not safe, and
   silently replacing a hand-written declaration would disable rules somebody meant.

## Rules

- **Never infer a missing gating value.** Reject and name it. A halt that depends on a value
  the compiler invented is not a halt.
- **Never compile a phase whose pattern is in the rejected list**, however the user phrases
  the request. `serial-fix-loop` in particular: say what the catalog measured about it and
  offer `best-of-n` instead.
- **Never widen `writeScope` to make a candidate fit.** The scope is the contract.
- Optional delegates (zirkel, andon) are compiled as *beats*, not as prose instructions. If
  the plugin is absent, drop the beat, use the bundled fallback, and say so plainly.

## Output format

```
arbeitsplan compile — run ap-2026-09-12-a3f1
  shape        change
  scope        src/api/search.py, src/api/limits/**, tests/test_ratelimit.py
  acceptance   3 criteria, 3 with runnable checks
  budget       9 dispatches / 25 min
  phases       build (best-of-n, fanOut 3, sonnet, auto, writes worktree)
               -> referee (blind-referee, 3, sonnet, auto, writes none)
               -> land (select-then-synthesize, 1, sonnet, auto, writes shared)
  delegates    zirkel:zirkel-explore-branches (installed) -> beat branches-explored
  backend      in-session  (why: writes-shared-tree)

wrote analysis/arbeitsplan/ap-2026-09-12-a3f1/workflow.json
takt beats NOT written — approval required. Writing them makes takt live and
fail-closed in this repository; it will deny a dispatch that runs ahead of its beat.

Next: arbeitsplan-run for the in-session swarm, or arbeitsplan-matrix for the
headless one (fresh process per candidate, real per-cell --model).
```

A refusal is an output, not an error:

```
arbeitsplan compile — REFUSED
  shape        question
  reason       "should we use Redis or Postgres for this" alters no files and has no
               runnable check, so a swarm would return three confident answers and no
               way to tell which is right.
  route        zirkel:zirkel-solve
  wrote        analysis/arbeitsplan/out-of-scope-reasoning.json
```

## Resources

- `references/workflow-spec-schema.md` — every key, and every compile-time rejection.
- `references/patterns.md` — the accepted patterns, and the rejected ones with the
  measurement that rejected them.
- `references/candidate-contract.md` — what the phases you compile will actually exchange.
- `references/backend-selection.md` — the backend decision table, via `arbeitsplan-backend`.
