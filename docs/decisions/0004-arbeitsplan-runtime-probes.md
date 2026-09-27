# ADR 0004 — measuring the runtime arbeitsplan depends on

::: info Snapshot
Dated decision record, 2026-09-27. It follows [ADR 0003](./0003-arbeitsplan-authored-steps-and-agent-gen.md).
It corrects two of the measured behaviours [ADR 0002](./0002-arbeitsplan-designs-and-waves.md)
records, and answers the two it left "to be probed". ADR 0002 and ADR 0003 stay as written.
File paths cite the tree as it stood that day.
:::

**Status:** Accepted, 2026-09-27.

## Context

arbeitsplan's code rests on five runtime behaviours that no reference documents, or documents
differently from what was once observed:

| probe | behaviour | code that depends on it |
|---|---|---|
| P1 | plan mode inside a linked worktree | the `arbeitsplan-design` SKILL's "still to be probed" |
| P2 | `--resume` of a session that ran `EnterWorktree` | the same, and `handoff.py`'s same-session path |
| P3 | prompt-cache reuse between sibling agents | `design-table-schema.md`'s "Efficient designs", tagged **unverified** |
| P4 | an agent type written mid-session | `handoff.py` (`NEW SESSION REQUIRED`), `install_waves.py`'s notice, two SKILLs |
| P5 | the commit an isolated agent's worktree starts from | `waves.js` (`PRIMARY CHECKOUT ONLY`, `WRONG BASE`), the `waves_state.py` preflight |

For P4 and P5, ADR 0002 recorded an observation from the #106 prototype on Claude Code 2.1.281.
For P4, the current docs say `.claude/agents/` is hot-reloaded within seconds. For P5, they
describe a `worktree.baseRef` setting. Both conflict with what the code assumed.

## Decision

Measure, don't argue. `plugins/arbeitsplan/scripts/probe_runtime.py` runs each behaviour as a
headless `claude -p` session in its own scratch repository. It decides every run from facts,
never from the model's prose:

- the files on disk and `git rev-parse`;
- the stream-json events: `system/init`, tool results, `task_notification`, `permission_denials`;
- the subagent transcripts and their `.meta.json`;
- each Workflow launch's own output file.

`--selftest` is the only part CI runs (`plugin-checks.yml`). It plants every oracle both ways
and replaces each one with a constant to prove a case goes red. It also drives the argv and the
turn driver end to end against a stub `claude`, and refuses an existing `--out`. CI proves the
instrument, never the runtime; the live sweep spends tokens and is run by hand:

```bash
python3 plugins/arbeitsplan/scripts/probe_runtime.py --probe all --n 3 --out analysis/probes/<stamp>
```

Runs are labelled and aggregated as follows:

- **ERROR** covers empty or truncated output, a limit banner, a timeout, a missing `result`,
  and a failed control. **Void** covers a run that never attempted the thing, a Workflow tool
  that was not offered, or a worktree that was not entered.
- Neither ERROR nor void runs count towards N.
- When all N valid runs agree, the verdict is HOLDS, CHANGED or NEW; any disagreement makes it
  INCONCLUSIVE.

## Results

Claude Code **2.1.283**, model haiku, N=3, 2026-09-27. **0 ERROR runs.** Every verdict's
transcripts were read before it was recorded here. Raw output is gitignored:

- P1, P2, P3 and P5: `analysis/probes/sweep-2026-09-27b`;
- P4: `analysis/probes/sweep-2026-09-27c-P4`, after the oracle fix below.

| variant | setup | runs | verdict |
|---|---|---|---|
| P1a | plan mode, cwd = a linked worktree, asked to write a file | MODEL_REFUSED ×3 (+1 void) | NEW |
| P1b | plan mode in primary, `EnterWorktree`, then write | MODEL_REFUSED ×3 | NEW |
| P1c | baseline: plan mode in primary, same request | MODEL_REFUSED ×3 | NEW |
| P1d | control: `acceptEdits` in the worktree | WROTE ×3 | HOLDS |
| P2 | session A enters a worktree; `--resume A` from primary | RESUMED_WT+RECALL ×3 | HOLDS the docs |
| P3a | three Agent-tool siblings of one type, one message | REUSE ×2, PARTIAL ×1 | INCONCLUSIVE |
| P3b | three Agent-tool siblings, different `tools` | NO_REUSE ×3 | HOLDS |
| P3c | three `agent()` calls of one type in a `parallel()` | REUSE ×3 | HOLDS |
| P4a | type written in the turn, then the Agent tool | NOT_FOUND ×3 | HOLDS ADR 0002 |
| P4b | type written in the turn, then Workflow `agent()` | NOT_FOUND ×3 | HOLDS ADR 0002 |
| P4c | as P4a, 30 s after the write | NOT_FOUND ×3 | HOLDS ADR 0002 |
| P4d | type written in turn 1, Agent tool in turn 2 | RESOLVES ×3 | **CHANGED** |
| P4e | type written in turn 1, Workflow `agent()` in turn 2 | RESOLVES ×3 | **CHANGED** |
| P5a | isolated agent (Agent tool), repo with a remote | REMOTE ×3 | **CHANGED** |
| P5b | isolated `agent()` from a Workflow, with a remote | REMOTE ×3 | **CHANGED** |
| P5c | isolated agent, no remote | PRIMARY ×3 | HOLDS ADR 0002 |
| P5d | with a remote and `worktree.baseRef: "head"` | CALLER ×3 | **CHANGED** |

What each result means:

- **P1: plan mode holds in a worktree, at the model layer.** In plan mode the model declined
  the write in the worktree exactly as it did in the primary checkout, and never called
  `Write`, so the harness never had anything to deny. A headless run cannot reach the
  harness's own refusal. The honest claim is only that a worktree does not change what plan
  mode does: it is neither a way around plan mode nor a second lock.
- **P2: resume returns to the worktree.** The resumed session's `init.cwd` was the entered
  worktree under `.claude/worktrees/`, and it recalled the code word, 3 of 3.
- **P3: identical `agent()` siblings share one prefix; Agent-tool siblings can race.**
  - **Workflow fan-out.** In P3c, one sibling created about 15.8k tokens of cache and the
    other two read all of it, every run.
  - **One message of Agent calls.** Usually the same, but in one run of three, two siblings
    created 15,655 tokens each before either could read it.
  - **Different `tools`.** Siblings never shared: each created its own 15.6k–16.7k.
- **P4: a later turn, not a new session.** An agent type written mid-session is not found in
  the turn that wrote it, even 30 s later. It resolves in the next turn, for the Agent tool and
  Workflow `agent()` alike. In `-p`, a background Workflow's completion notification starts a
  turn of its own; in sweep b, a model relaunched the failed run with `resumeFromRunId` in that
  woken turn and the type resolved there.
- **P5: an isolated worktree starts from `worktree.baseRef`.**
  - **With a remote**, it starts from the remote's default branch, not from the primary
    checkout's HEAD.
  - **Without a remote**, it starts from the primary's HEAD.
  - **With `"head"`**, it starts from the caller's HEAD.

  The worktree is created under the primary repository's `.claude/worktrees/` in every case.

## Instrument defects the sweeps found

Each one produced a plausible tally, and each was found by reading transcripts, not the tally.

| sweep | symptom | cause | fix |
|---|---|---|---|
| smoke | P1 all NO_ATTEMPT (void) | the model declines in plan mode before any tool call | `MODEL_REFUSED`, when the reply cites plan mode; P1c's assumed DENIED claim dropped |
| smoke | Workflow launches refused | `-p` asks to "review dynamic workflow before running" | the per-run settings allow `Workflow` |
| 2026-09-27 | P4b PRESENT_AT_START 5 of 6 | a later turn's `init` was read as the first | the oracle reads the FIRST `init` |
| 2026-09-27 | P2 lost recall 2 of 3 | only the final text block was read | all text blocks |
| 2026-09-27 | P3 bases picked wrong | siblings ordered by transcript timestamps, which stamp a response's END | an order-free rule: exactly one creator, the rest read ≥80% |
| building P4d/e | "two turns" were one | `--input-format stream-json` with both messages written at once is ONE turn | `run_turns` writes each message after the previous `result`, and a dead process is ERROR |
| 2026-09-27b | P4b RESOLVES 1 of 3 | a `resumeFromRunId` relaunch overwrites `workflows/<runId>.json` | the oracle reads the FIRST launch's own output file |
| 2026-09-27b | model prose counted as a runtime error | a loose not-found pattern | only the runtime's exact `agent type '…' not found` |

## Consequences

| finding | change |
|---|---|
| P4 | `handoff.py` reports `laterTurnRequired` and says `LAUNCH IN A LATER TURN`. It still names the new types and prints a fresh session's start prompt, which works on any CLI version. New types no longer forbid the same session. The same change reaches `install_waves.py`'s notice and runbook, the waves and design SKILLs, and the README. |
| P5 | `waves.js` keeps both halts; the wrong-base halt now names `worktree.baseRef` as the cause and the two remedies. The `arbeitsplan-waves` SKILL, the runbook and the preflight docstring say where a builder's worktree starts. `test_waves_workflow.js` asserts the halt names it. |
| P1, P2 | The design SKILL states both findings in place of "still to be probed". |
| P3 | The "Efficient designs" row is **measured**, not **unverified**, and says the Agent tool can race. |
| tags | "**measured**" now means observed in the #106 prototype or by `probe_runtime.py`, with its CLI version. |

The `PRIMARY CHECKOUT ONLY` halt stays. It no longer rests on "worktrees branch from the
primary's HEAD", which is true only without a remote. It rests on what `waves.js` does itself:
the preflight measures the wave base, and the merge gate switches branches, in the primary
checkout.

## Correcting ADR 0002 and ADR 0003

ADR 0003 repeats two measured behaviours from ADR 0002 as still undocumented. On 2.1.283:

- "Worktrees branch from the primary checkout's HEAD" holds only without a remote. Otherwise
  a worktree starts from `worktree.baseRef`, which by default is the remote's default branch.
- "Agent types added mid-session do not resolve" holds only for the turn that added them.

Both were true as observed; neither was the whole rule. Re-run the probe after a CLI upgrade
before trusting either, including the corrected forms above.
