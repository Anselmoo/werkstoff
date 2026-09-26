# ADR 0001 — arbeitsplan scope boundaries (#62, #82, #83, #92)

::: info Snapshot
Dated decision record, 2026-09-26. Line numbers and file paths cite the tree as it stood that
day and are kept as a record, not updated. A later change that reverses one of these decisions
should supersede this record with a new ADR rather than edit it.
:::

**Status:** Accepted, 2026-09-26.

## Context

Four open issues against `arbeitsplan` asked scope questions, not for code:

- [#62](https://github.com/Anselmoo/werkstoff/issues/62) asks who owns a multi-link chain,
  since arbeitsplan compiles one change and takt enforces an order it does not decide.
- [#82](https://github.com/Anselmoo/werkstoff/issues/82) points out that the host Workflow
  tool's resume is undocumented next to arbeitsplan's own.
- [#83](https://github.com/Anselmoo/werkstoff/issues/83) proposes a `judge-patch` pattern.
- [#92](https://github.com/Anselmoo/werkstoff/issues/92) reports that Open and Verify phases
  are missing from the published phase model, and adds a side question about a stale catalogue.

None of them has a diff whose correctness a referee could check. So they were settled in one
reasoning session under plan mode that **dispatched nothing** (no Workflow run, no subagent), not
compiled into a swarm. Compiling a swarm for a question is what `arbeitsplan-compile` itself
refuses: *"three confident answers and no way to tell which is right."*

One rule governs every section below: **a decision names what it rejected and why, or it is not
a decision.**

## Decision

### #62 — the multi-link chain belongs to the consumer

**Decided: option 3, neither.** werkstoff stops at one compiled change plus an enforced order.
The chain layer (run links, gate links, `precedes`, `alternatives[]`, per-node budgets) belongs
to the consuming repository. This record exists so the boundary is read next time rather than
rediscovered.

**Rejected: option 1, extend `arbeitsplan`.**

- A gate link has no runnable check by definition, because a human answers it. Yet
  `arbeitsplan-compile` refuses a spec in which no criterion carries a runnable check
  (`plugins/arbeitsplan/skills/arbeitsplan-compile/SKILL.md:38`), and it refuses a
  question-shaped problem outright. The issue calls that refusal correct.
- Compiling gates would therefore mean weakening the two refusals that make a spec refereeable.
- arbeitsplan's convergence rule is "widen within one `writeScope`", and it has no meaning
  *across* scopes. Backtracking over unexplored alternatives between changes is planning.
- arbeitsplan's own records would not fix the survival problem either. `/analysis/` is
  gitignored (`.gitignore:23`), exactly like `.takt/`.

**Rejected: option 2, a thirteenth plugin.**

- The issue's own constraint defeats it. The consumer forbids a visible dependency on this
  marketplace. A chain plugin whose schema has to live in consumer repositories is that
  dependency again, one level up.
- The measured delta is three enum values in the consumer's existing node-graph schema. Against
  that, a plugin here carries fixed cost for one consumer's need: a report viewer, a
  `beats.json`, four release lists, and a zero ruff baseline.
- A planner has no tool call to deny. This repository measured that only `PreToolUse` hooks
  actually enforce, and the advisory `zirkel` rebuild gained nothing. takt already says it is
  "**not** a planner" (`plugins/takt/README.md:31`). A chain plugin would be exactly that
  planner, with nothing to enforce.

**What werkstoff does own: the seam.** No code change is needed.

- A run link in a consumer's chain names one `analysis/arbeitsplan/<runId>/workflow.json`.
- Its terminal state is `complete.json` (landed) or `FAILED-<stamp>.json` (halted, carrying
  the reason). Both are written by `record_event.py finish`
  (`plugins/arbeitsplan/scripts/record_event.py:32-33`, `:425-426`).
- That pair is the entire interface a chain needs to read.

**Reopen when:** a second, independent consumer rebuilds the same chain layer. The need is then
measured, not inferred from one repository.

### #82 — resume: document what arbeitsplan controls, and nothing else

**Decided: accept, narrowed.** A short section in
`plugins/arbeitsplan/skills/arbeitsplan-run/SKILL.md`, under "The workflow backend", will state:

1. arbeitsplan resumes by `startAt` + `carry`, and loop state lives in the calling skill, never
   in the script (`plugins/arbeitsplan/workflows/run.js:281-303`; `SKILL.md:263-266`).
2. **An arbeitsplan relaunch never passes the host's `resumeFromRunId`.** Phases before
   `startAt` are not called at all. The insulation #82 calls "partly by accident" is the design,
   and the section says so.
3. Editing `workflow.json` between relaunches makes a new contract. Re-compile under a new
   `runId`; do not relaunch. This is the same rule as "Never raise the budget mid-run. That is a
   decision to re-compile" (`SKILL.md:300`) and `scope-prover` refusing to widen a scope mid-run
   (`plugins/arbeitsplan/agents/scope-prover.md:19`).
4. Host behaviour is quoted only as the Workflow tool's own self-description, dated and marked
   **unverified by this repository**. On 2026-09-26 that description said resume is opt-in via
   `resumeFromRunId`, returns cached results where `(prompt, opts)` are unchanged, and works
   within the same session only.

**Rejected:**

- **Asserting host replay semantics as fact.** No artifact in this tree can verify them. A
  confident sentence about runtime behaviour nobody checked is the "looks correct and silently
  does nothing" shape this repository keeps paying for.
- **A new `references/` file.** Under `M-REF-UNWIRED` a new reference is a wiring task, and the
  content is about eight lines that belong beside the resume steps they qualify.
- **A spec-hash guard, inside this issue.** The guard would be `carry.specHash`, with `run.js`
  refusing a resume whose spec hash differs. It is the enforcing form and is worth doing, but it
  is code that needs its own `test_run_workflow.js` case. Folding it into a
  documentation-labelled issue would land an uncalibrated guard. It is recorded as its own
  follow-up.

### #83 — `judge-patch`: rejected as specified

**Decided: reject the proposal as written.** A narrowed form is accepted in principle, but only
as its own compiled change. **No index entry until then.**

**Rejected: resuming the same judge to confirm.**

- The judge authored the fix, so confirming it is self-review by the party holding the case.
  That contradicts the accepted, measured `blind-referee` rule
  (`plugins/arbeitsplan/references/patterns.md:78`, citing
  `plugins/matrize/agents/decode-referee.md:18-20`).
- It also contradicts the rejected `build-and-verify-in-one-dispatch`
  (`docs/orchestration/references/delegation.md:185-187`).
- #83's safety argument, that nothing is re-authored and the stop is arithmetic, holds for the
  *apply* step only. The *confirm* step is an opinion.
- The nearest precedent in this repository, `nacharbeit-fix`, confirms with a **blind**
  verifier, never the remediator (`plugins/nacharbeit/skills/nacharbeit-fix/SKILL.md:37-40`).

**Rejected: adding the id to the machine-readable index on its own.**

- `compile_spec.py` would then accept `pattern: "judge-patch"`, but no phase could execute it.
- `KINDS` (`plugins/arbeitsplan/scripts/compile_spec.py:38`) has no script-applied phase, every
  phase requires an agent `agentType`, and `run.js` has no branch that applies edits.
- An id the compiler accepts and no backend runs is the "documented but invisible" failure the
  index exists to prevent (`patterns.md:27-30`).

**Accepted in principle.** The narrowed shape is:

1. The judge emits `(file, exact phrase, replacement, expectedCount)` tuples, never prose.
2. A script applies them and exits non-zero on zero matches or on more than `expectedCount`.
3. A **fresh** `blind-referee` judges the resulting diff.
4. The evidence column honestly reads `reasoned`, because nothing here has measured it.
5. The entry carries an explicit contrast against `serial-fix-loop`.

It needs a phase kind, compile support, a `run.js` branch, and an apply script with its own
`--selftest`. That makes it a change to compile, not a catalog edit.

### #92 — Open and Verify: no new phase names

**Decided: Open is already modelled but not surfaced. A wide agentic Verify is rejected in
favour of the script that already does it.**

**Open already exists.** The schema's "six-phase shape"
(`plugins/arbeitsplan/references/workflow-spec-schema.md:289-302`) compiles it:

- INVENTORY: `fanout-readonly`, `map-reduce-disjoint`, `arbeitsplan:inventory-extractor`,
  haiku.
- CONTRACT: `arbeitsplan:contract-author`, opus, plan mode.

The real defect is discoverability. The README diagram (`plugins/arbeitsplan/README.md:32-42`)
and the output examples of `arbeitsplan-compile` and `arbeitsplan-patterns` show only
build → referee → land. **Accepted follow-up (docs):** point all three at the six-phase shape.

**Rejected:**

- **Verify as a wide agent phase.** "Run the checks, report what went red, decide nothing" is
  exactly what `reconcile.py --run-checks` does. It runs each check in code, hashes stdout,
  appends one attributable `execute_tool` event per check, and gates landing (#76), all at zero
  dispatches. Eighteen agents doing the same thing reintroduce transcribed exit codes, which #76
  replaced ("MEASURES rather than transcribes", `plugins/arbeitsplan/scripts/reconcile.py:19`).
- **Folding Verify into Referee.** The referee is starved by design: criteria and diff only.
  Handing it gathered evidence widens exactly the input it must not see.
- **A cost-estimate multiplier derived from the reported run.** The run is n=1, as the issue
  itself says. A constant fitted to it would be an oracle retuned to its subject.

**Q3, the cost estimate.** The estimate sums the compiled phases' `fanOut`. An Open performed by
hand is uncounted because it is uncompiled. The fix is to compile it as INVENTORY and CONTRACT,
not to pad the estimate.

**Open follow-up (a diff).** Step 8 of `arbeitsplan-run` measures only the *winner* before
landing. Running the same script over every measured candidate before refereeing would give each
verdict a named check, still at zero agents.

**Side question: the stale deployed catalogue.**

- The source is clean. `docs/` names none of `self-assess`, `confab`, `compass` or
  `codebase-consistency` as a plugin. Only the deployed site is reported to lag, and this
  session did not verify the deployed site.
- **Decided:** split it into its own docs/deploy issue.
- **Rejected:** fixing it inside #92. It has a different fix owner (the docs deploy) and would
  keep #92 open on an axis that has nothing to do with phases.

## Consequences

This record lands no code. Each follow-up below is its own future change, compiled or written
separately:

| from | follow-up | kind |
|---|---|---|
| #82 | resume section in `arbeitsplan-run/SKILL.md` ("The workflow backend") | docs |
| #82 | `carry.specHash` resume guard in `run.js`, with a `test_run_workflow.js` case | code, new issue |
| #83 | narrowed `judge-patch`: phase kind, compile support, `run.js` branch, apply script with `--selftest`, then the index entry | code, compiled change |
| #92 | README diagram and the compile/patterns output examples point at the six-phase shape | docs |
| #92 | measure every measured candidate with `reconcile.py --run-checks` before refereeing | code, new issue |
| #92 | deployed catalogue vs. `plugins/` directory check | docs/deploy, new issue |

#62 has no follow-up by design. Its reopen condition is stated above.
