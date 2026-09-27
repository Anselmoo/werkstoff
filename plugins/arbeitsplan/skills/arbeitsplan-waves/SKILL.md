---
name: arbeitsplan-waves
description: Installs an approved multi-wave design into a project as project-owned files — a pinned interpreter, the plan, a state helper, a path and runner guard, and one agent file per agent type — then launches and resumes it from the primary checkout. Use when a restructuring needs several waves of parallel, disjoint rows, each building on the merged and gated result of the last; when a hand-written multi-wave workflow should become a table; or when a stopped wave run must be resumed. The installed files run without werkstoff. Runs nothing it has not been asked to; a red gate or a pending human gate stops the run, never a retry.
argument-hint: "install <design.json> | launch <name> | resume <name> | approve <name> <gate-id>"
---

# Multi-wave runs

`arbeitsplan-run` runs **one** change: N candidates over one scope, and exactly one lands.
Some restructurings are larger than one change. They need several rows of *different* work
per wave, each wave built on the merged result of the one before. This skill installs that
kind of run into the project and drives it. The design comes from `arbeitsplan-design`, and
`references/design-table-schema.md` is its contract.

Each requirement below comes from a failure observed in a hand-written prototype (#106), and
each is a check in code rather than a sentence here:

- the run refuses to start from a linked worktree;
- every row starts with `git merge --ff-only <wave base>`, and the run halts on a wrong base;
- a finished wave is skipped before any of its builders is dispatched;
- merges go into an integration branch, and the target moves only on a green gate;
- gates run twice, once in the primary checkout and once in a clean worktree, so a finding
  that only the primary checkout shows is labelled `primary-only`;
- a swarm row's losers are discarded, never merged;
- prompts carry ids and branch names only;
- an **authored** step is written by a shell-less author and verified (syntax, a sample in a
  scratch worktree, the output schema) before anything runs it, and the guard refuses to run
  it once its file or its contract has changed.

## Install (once per design)

1. The design must already be approved and written. `compile_spec.py --design --write` prints
   its sha256. Refuse a design whose hash differs from the approved one.

2. Install:

   ```bash
   python3 -B "${CLAUDE_PLUGIN_ROOT}/scripts/install_waves.py" \
     --design analysis/arbeitsplan/<runId>/design.json [--artifact]
   ```

   Pass `--artifact` when the repository is itself an installable artefact, so the generated
   tooling is `export-ignore`d.

   A design with **authored steps** gets a skeleton per step under
   `.claude/workflows/<name>.steps/` (gitignored), in the language its runtime names, plus a
   `<name>-author` agent. The first launch writes and verifies them; re-installing never
   overwrites a step that is no longer a stub.

   The installer resolves the one prerequisite, a Python >= 3.10 for the helper and the guard,
   by probing `python3`, `python` and `py -3`, or the command given with `--python`. That
   interpreter is written into every command. The installer refuses to overwrite any file it
   did not generate.

3. **Tell the user to start a fresh session.** Agent types added mid-session do not resolve in
   `agent()`. The installer prints this, and `handoff.py plan` repeats it together with the
   exact start prompt. Do not launch from the session that ran the install.

## Launch and resume

1. **From the primary checkout.** Agent worktrees branch from the primary checkout's HEAD, not
   the caller's. The interpreter's preflight halts on a linked worktree and on tracked changes;
   do not try to route around it.

2. Read the state and launch:

   ```bash
   python3 .claude/workflows/<name>_state.py show
   ```

   Launch the Workflow tool with `scriptPath: .claude/workflows/<name>.js` and
   `args: {plan: <the parsed .claude/workflows/<name>.plan.json>, state: <that output>}`.
   Pass both **as objects**; a JSON string is refused. There is no cost cap by default.
   Subscription limits stop the run, and relaunching with the saved state is the whole resume.

3. **Read the result, and act on its shape:**

   | result | what to do |
   |---|---|
   | `aborted: false` | report the final `integrationSha` and that the target moved; done |
   | `pending_human_gate: <id>` | show the user what that gate approves. On their yes, run `<name>_state.py approve --gate <id>`, then relaunch |
   | `abortReason` names a red gate | report `findings` with each one's `source` (`primary-only` means only the primary checkout's untracked or ignored files produced it) and the `kept` worktrees. **Do not retry.** A fix is a new row or a new design |
   | `WRONG BASE` or `PRIMARY CHECKOUT ONLY` | the launch site is wrong; relaunch from the primary checkout |
   | `SCRIPT CONTRACT` | a declared command exited unexpectedly or printed output that breaks its schema: a defect in the step, not a flake |
   | `AUTHOR CONTRACT` | an authored step was refused by `verify-step` after its node's `retries`. Report the `problem` and the `step` path. Read the file; the fix is a sharper `purpose`, a better `sample`, or more `retries` in a new design, never a hand edit the hash would refuse anyway |

   `show` reports each authored step as `missing`, `stub`, `authored`, `verified` or `stale`.
   Only `verified` is skipped on the next launch. To re-check a step by hand, run
   `<name>_state.py verify-step --node <id>`.

   The state helper persists its state as the run goes. Every finished builder is recorded the
   moment it returns, and every green wave when its gate passes, so a relaunch skips both.

## Rules

- **Never merge by hand to "help" a stopped run.** The integration branch and the kept
  worktrees are the evidence; the next launch or a new design moves forward.
- **Never widen `offLimits` or edit the generated guard** to get a row through. The guard is a
  hook because a permission rule did not hold inside agent worktrees.
- **The installed files are the project's.** A new round of work is a new design and a new
  install, never an edit to the generated interpreter.

## Output format

```
arbeitsplan-waves rebuild-cli — launched from /work/proj (primary checkout)
  preflight   head 4e1a9c0, clean, python 3.12.3
  wave 1      w1-parse ✓  w1-render ✓   gate-1  green (go vet, go test: both trees)   main → 7b2d110
  wave 2      w2-cli ✓                  gate-2  RED
                test   primary-only  exit 1   (clean worktree: exit 0)
              kept: agent/w2-cli (worktree .claude/worktrees/w2-cli)
STOPPED at gate-2: main is still 7b2d110. The failure appears only in the primary checkout —
an untracked or ignored file there. Inspect it; this run does not retry.
Resume after the fix: relaunch with `rebuild-cli_state.py show` — wave 1 will be skipped.
```

## Resources

- `references/design-table-schema.md` — the design, the wave rules, the rejections.
- `references/patterns.md` — `gated-disjoint-waves`, and why only this form of
  merging different work is admissible.
- `scripts/install_waves.py`, `scripts/waves_state.py`, `scripts/waves_guard.py`,
  `workflows/waves.js` — what gets installed, each with its own selftest.
