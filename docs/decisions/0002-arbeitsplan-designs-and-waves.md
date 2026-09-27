# ADR 0002 — arbeitsplan designs, script nodes and waves (#106, #107)

::: info Snapshot
Dated decision record, 2026-09-27. It partly supersedes [ADR 0001](./0001-arbeitsplan-scope-boundaries.md)'s
#62 section and records what landed of its #83 section. File paths cite the tree as it stood
that day and are kept as a record, not updated.
:::

**Status:** Accepted, 2026-09-27.

## Context

- [#106](https://github.com/Anselmoo/werkstoff/issues/106) asks for a **multi-wave** mode.
  Several rows run per wave, in parallel, and each wave builds on the merged result of the one
  before. It lists ten requirements, each from a failure observed in a hand-written prototype
  in a second consumer repository. A follow-up comment checked six more proposals against the
  Workflow and worktree docs.
- [#107](https://github.com/Anselmoo/werkstoff/issues/107) asks for a **design step** before
  anything runs: what, where, when and how per node. It also asks for **script nodes** in any
  language.

Both issues were written after observing **one** project. A review of the first
implementation slice found that project's ecosystem in the design itself:

- a closed runtime whitelist;
- gates hard-coded in a helper;
- "install the package" as the smoke test;
- a file-disjointness rule that only works where adding a module needs no registration edit.

The decisions below were checked against that bias as well as against the issues.

## Decision

### #62 reopened, and the seam still holds

ADR 0001 kept the multi-link chain out of arbeitsplan, with an explicit reopen condition: *"a
second, independent consumer rebuilds the same chain layer."* #106 is that second consumer.
The need is now measured.

**Decided:** a multi-wave plan is a **design table**, interpreted by a **pinned, vendored**
interpreter (`workflows/waves.js`). `install_waves.py` copies it, with its state helper and
its guard, into the consuming repository, where it runs **without werkstoff installed**.

**Rejected: generated bespoke JS per plan.** A new round of work would become a new script,
and schema drift would move into generated code no check reads. A pinned interpreter plus a
table makes a new round a new table. This follows #106's own comment.

**What stays true from ADR 0001:**

- The consumer still owns its chain. The installed files are the project's, and werkstoff is
  not a runtime dependency.
- A human gate still has no runnable check. So it is a node **between** workflow runs, never
  inside one, and the validator (`AP-HUMAN-GATE-INSIDE`) refuses a gate that does not cut the
  graph in two.

### The rejected `partition-then-merge-worktrees`: narrowed, not reversed

The rejection's grounds were that conflicts reappear at integration, where they cost more. The
accepted `gated-disjoint-waves` form removes those grounds, and each part is enforced in code:

- **Disjoint ownership is proved mechanically**, for concurrent rows only
  (`AP-WAVE-SCOPE-OVERLAP`, via `land_candidate.scope_overlap`). The check is conservative and
  case-folded: it may call a disjoint pair overlapping, never the reverse.
- **A gate runs after every wave, and the target moves only on green.** Merges go into an
  integration branch first.
- **Each row starts from its wave's base** with `git merge --ff-only`. The interpreter halts
  on a wrong `baseSha`.

An **integrator** row runs after its wave's rows, on their merge. It owns the module manifest
and lockfile that most ecosystems edit per new module. Without it, the disjointness rule would
reject almost every non-Python wave.

Unproven partitions merged at the end remain rejected.

### #83: the script-applied phase, landed in its narrowest form

**Landed:** phase kind `script` (pattern `script-step`), and design nodes of kind `script` and
`merge-gate`.

- Each runs **one declared command** through a runner agent whose only tool is Bash.
- A guard allows exactly that command, once per dispatch:
  - `hooks/arbeitsplan_guard.py`, keyed on the hook input's `agent_type` and `agent_id`;
  - in an installed project, the generated `<name>_guard.py`.
- The result `{exit, stdout_digest, parsed}` is checked in code against `expectExit` and a
  strict `outputSchema`.

**Not landed: `judge-patch` itself.** A `script` phase writes `none`. It runs gates, runners
and state helpers, and returns data. Applying a judge's edit tuples, and blind-refereeing the
result, is still the separate compiled change ADR 0001 describes. `judge-patch` is still absent
from the index.

**Rejected: a closed list of script runtimes.** The first slice's whitelist
(python, uv, julia, cargo, node, bash) came from the one observed project.

- A command now names a **toolchain**: a broad built-in starting set, or one the design
  declares. Its argv[0] must match that toolchain's executables.
- Preflight runs the toolchain's probe, and exit 0 is the whole test.
- Gates and smoke steps are declared by the design (`AP-GATES-UNDECLARED`,
  `AP-SMOKE-UNDECLARED`), never supplied as defaults.

### The one runtime prerequisite: Python, declared and resolved

The vendored helper and guard are stdlib-only Python >= 3.10. `install_waves.py` **resolves**
the interpreter by probing `python3`, then `python`, then `py -3`, and writes the one that
answers into every command it generates. Each generated hook command ends in `|| exit 2`, so an
interpreter that cannot start **denies** instead of passing.

**Rejected alternatives:**

- **Node,** which is not guaranteed on every Claude Code install.
- **Bash,** which is worse on Windows and for handling JSON.

A subprocess helper is needed in any case, because a Workflow script cannot exec anything.

### AP-BASE-BACKEND stays

`run.js` still cannot seed a candidate worktree from a prior wave's winner, so `base` under the
workflow backend stays rejected. The wave interpreter handles bases itself, with the
`--ff-only` merge and the `baseSha` check. It does not need `base`.

## Measured, undocumented behaviour this depends on

- `agentType` and `isolation: 'worktree'` as `agent()` options from a Workflow script.
  Neither is documented for workflows as an agent() option. The prototype measured both on
  Claude Code 2.1.281. `test_waves_workflow.js` asserts which options `waves.js` passes, so a
  change to them is visible in review.
- Agent worktrees branch from the **primary checkout's** HEAD, not the caller's.
- Agent types added mid-session do not resolve in `agent()`. `install_waves.py` and
  `handoff.py` both require a fresh session when a design creates one.

Two things are still to be probed rather than assumed: plan mode inside a worktree, and resume
across `EnterWorktree`.

## Consequences

| what | where |
|---|---|
| design table contract and rejections | `plugins/arbeitsplan/references/design-table-schema.md` |
| validator, one red fixture per tagged rule | `scripts/design_spec.py`, `scripts/fixtures/red/*.design.json` |
| script phase, runner agent, guard | `workflows/run.js`, `agents/script-runner.md`, `hooks/arbeitsplan_guard.py` |
| wave interpreter and vendored files | `workflows/waves.js`, `scripts/{waves_state,waves_guard,install_waves}.py` |
| skills | `arbeitsplan-design`, `arbeitsplan-waves` |
| catalogue | `script-step`, `gated-disjoint-waves` accepted; `partition-then-merge-worktrees` narrowed |
