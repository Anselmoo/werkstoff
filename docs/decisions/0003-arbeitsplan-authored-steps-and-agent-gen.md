# ADR 0003 — authored steps, generated agents, the runbook and the design report

::: info Snapshot
Dated decision record, 2026-09-27. It follows [ADR 0002](./0002-arbeitsplan-designs-and-waves.md)
and changes none of its decisions; it corrects one of its "undocumented" findings (below). File
paths cite the tree as it stood that day.
:::

**Status:** Accepted, 2026-09-27.

## Context

A follow-up to #106 and #107 asked four questions:

1. **Should a workflow folder hold Python, bash or Ruby next to the JavaScript?**
2. **Does a workflow need a markdown file?**
3. **Does arbeitsplan need an agent generator for its workflows?**
4. **Can a workflow be seen, as a picture, before and while it runs?**

It also asked what makes a Claude Code workflow efficient.

The answers came from the Workflow runtime reference, the Claude Code docs, and the tree:

- **Only `.js` in `.claude/workflows/` is a workflow.** Every other file there is ignored: not
  listed, not run, and not an error. `export const meta` is a workflow's only metadata.
- **A Workflow script cannot execute anything.** No `fs`, no `child_process`, no `import()`.
  A Python, bash or Ruby file beside it is never run by the runtime. And every check in this
  repository (`check-js-syntax.sh`, `check_workflow_models.py`, nacharbeit's `S-WF-*`, the
  surface index) reads only `workflows/*.js`. Such a file would be the "looks correct and
  silently does nothing" defect.
- **`install_waves.py` already generated agent files, but dropped design keys.** It
  hard-coded `tools` per role and dropped `effort` and `skills`, all three of which
  `design_spec.py` had validated. `waves.js` never passed `effort` either.
- **Nothing drew a design or a run as a graph.** `run-viewer.html` shows one swarm run's
  candidates.

## Decision

### Scripts in other languages: authored steps, not files beside a workflow

A design's `script` node may **author** its step: `script.author = {model, purpose, sample}`.
The plan writes the script, in the language its `runtime` names, then verifies it before
anything runs it. There are five authorable runtimes, and each has a template and a syntax check
that does not execute the file:

- `shell` → `bash`
- `powershell` → `pwsh`
- `ruby`
- `node` → `.mjs`
- `python`

**Rejected: a design key for the path or the language.** The runtime is the language, and the
path is fixed at `.claude/workflows/<name>.steps/<id>.<ext>`. Two keys that could only disagree
with something else are two keys a design cannot get wrong.

**Rejected: `.js` for node steps.** Claude Code would treat the step as a workflow.

**Rejected: authoring in `run.js` specs.** Nothing there would write the file, so the key is
refused (`compile_spec.py`), not ignored.

The lifecycle, and where each step is enforced:

| step | enforced by |
|---|---|
| a skeleton per step, with the stub marker, never over an authored file | `install_waves.py`, `test_authored_steps.py` |
| a shell-less author writes one step file per dispatch | the agent's fixed tools; `waves_guard.py --author` |
| syntax without execution, the sample in a throwaway worktree, stdout against the strict schema, then `{sha256, contract}` recorded | `waves_state.py verify-step` |
| the runner refuses a step never verified, edited since, or whose contract changed | `waves_guard.py --runner` |
| a verified step is skipped on resume, and a stale one is rewritten | `show` computes each status from disk, and `waves.js` trusts only that |

**The steps directory is gitignored.** The preflight refuses a checkout with tracked changes,
so committed stubs would dirty it the moment an author filled one. The consequence: an authored
step cannot be a wave gate, because gates also run in a clean worktree, which has no ignored
files. Authoring is confined to `script` nodes for that reason.

**The hash, not `offLimits`, protects an authored step.** Every builder has Bash, and Bash
writes around any Edit hook. A hash compared at the moment of execution cannot be written around.

### A markdown file: a runbook for people, never for the runtime

A workflow needs no markdown. But the installed tooling runs without werkstoff, so
`install_waves.py` writes `.claude/workflows/<name>.md`, which the runtime ignores. It holds:

- the files, and launch and resume;
- what each result means;
- the node table, with the commands **as installed**;
- the authored steps;
- how to draw the plan.

It is derived from the design alone, so a re-install writes it byte for byte.

### Agents: one generator, and the design's keys reach it

`scripts/agent_gen.py` is the one generator; `install_waves.py` and `handoff.py` both call it.

- **`tools` and `skills` belong to the definition.** They go into the file, and nodes that
  share a type must agree on them (`AP-AGENT-CONFLICT`).
- **`model` and `effort` belong to the dispatch.** `waves.js` passes each node's own; the file
  holds only a default.
- **Keys that would reach no file are refused.** A wave design that declares `tools` or
  `skills` on a type it does not generate is rejected (`AP-AGENT-KEYS-UNAPPLIED`).
- **Fixed tools for two roles.** The runner (Bash only) and the new author (no Bash) cannot
  have their tools overridden, because their guard modes depend on those tools.

### Seeing it: `design-viewer.html`

`scripts/build_design_html.py` draws a design top to bottom by longest-path layering:

- waves are bands;
- a human gate is a line where one run ends;
- two concurrent rows that may write the same file are joined by an overlap arc;
- each node's what, where, when and how is one click away.

With the run helper's `show` output it adds the run's state. With a compiled `workflow.json` it
adds the phases.

Everything on the page is computed by the code that decides it:

- rejections come from `design_spec.py`;
- overlaps come from `land_candidate.py`;
- statuses come from `show`;
- the phases come from `compile_spec.py`;
- "installed" comes from preflight results, so a toolchain nobody probed reads "not probed".

It is wired into four skills: `-design` (before approval), `-waves` (after every launch),
`-compile`, and `-status` (on request only, because status writes nothing).

**Rejected: a new skill.** The viewer serves steps four skills already own.

**Rejected: d3 or a force layout.** A design has tens of nodes, and a force layout moves them on
every render.

**Rejected: a left-to-right layout.** Designs are long and narrow, and sideways they shrink
past reading.

### Efficient workflows, recorded where designs are written

`references/design-table-schema.md` gains an "Efficient designs" table. It tags each practice
**enforced**, **documented**, **measured** or **unverified**. Two changes to `waves.js` came
out of it:

- **Effort per dispatch.** `waves.js` now passes `effort` on every dispatch that declares it.
- **The author phase pipelines.** Each step goes author → verify on its own, and only the
  verifies are serialized. `test_waves_workflow.js` asserts both, with timed stubs and a
  sabotage apiece.

## Correcting ADR 0002

ADR 0002 lists `agentType` and `isolation: 'worktree'` as undocumented `agent()` options,
measured on Claude Code 2.1.281. The Workflow runtime reference now documents both, and
`effort` with them. ADR 0002 is a snapshot and stays as written; the two measured behaviours it
records beyond that remain undocumented:

- worktrees branch from the primary checkout's HEAD;
- agent types added mid-session do not resolve.

## Consequences

| what | where |
|---|---|
| authored steps: rules, templates, helper, guard, installer | `design_spec.py` (`AP-AUTHOR-*`), `assets/step-templates/`, `waves_state.py verify-step`, `waves_guard.py --author`, `install_waves.py` |
| the Author phase | `workflows/waves.js`; `test_waves_workflow.js` |
| end to end, five languages | `scripts/test_authored_steps.py` (CI sets `ARBEITSPLAN_REQUIRE_TOOLCHAINS=1`: a skipped language fails) |
| the agent generator | `scripts/agent_gen.py`; `AP-AGENT-CONFLICT`, `AP-AGENT-KEYS-UNAPPLIED` |
| the runbook | `install_waves.py` → `.claude/workflows/<name>.md` |
| the design report | `assets/design-viewer.html`, `scripts/build_design_html.py`, `scripts/fixtures/design-demo.json` |

**One defect caught before it shipped.** The PowerShell parse check was filled by
`str.replace` with `str.format`-doubled braces. That turned its `exit 1` into an unexecuted
scriptblock literal, so a broken `.ps1` exited 0. Local testing with pwsh 7.4.6 showed it, and
`test_authored_steps.py` now asserts the rendered command.
