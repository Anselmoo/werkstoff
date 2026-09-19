# Backend selection — matrix, workflow, or in-session

`workflow.json`'s `backend` used to be a bare string that `compile_spec.py` type-checked and
nothing else read. A run was then forced into whichever backend the session happened to reach
for. This reference is the decision, and `backend.why` records which row made it.

**Contents** — [the three backends](#the-three-backends) · [the decision table](#the-decision-table) · [the why vocabulary](#the-why-vocabulary) · [what the compiler refuses](#what-the-compiler-refuses) · [the unhooked gap](#the-unhooked-gap) · [the token argument](#the-token-argument-recorded-as-reasoned)

## The three backends

| backend | one candidate is | who writes the shared tree | what enforces the contract |
|---|---|---|---|
| `in-session` | an `Agent` dispatch from this session | this session, under the hook | `arbeitsplan_guard.py` sees every dispatch and write |
| `matrix` | a fresh `claude -p` process (`run_matrix.sh`, `subrun.py`) | nobody during the sweep; a cell's diff is evidence | the clean box, the isolation sentinel, `score_cell()` |
| `workflow` | an `agent()` call inside `workflows/run.js` | nobody inside the workflow; this session lands afterwards | code in `run.js` (breaker, filters, selection rule), then the hook at landing |

## The decision table

First match wins. Rows are ordered by which constraint is **structural** — a fact the backend
cannot change — before any that is a preference.

| # | if | then | `why` id | because |
|---|---|---|---|---|
| 1 | a skill, agent or hook under test was **edited this session** | matrix | `edited-this-session` | definitions load once per session; an in-session dispatch grades the pre-edit file |
| 2 | the question is **does it fire**, or plugin-present vs absent | matrix | `does-it-fire` | measured: `compass-clarify-scope` 0/12 is obtainable only from a fresh process with a controlled `--plugin-dir` |
| 3 | **per-candidate model tier is the variable** | matrix | `tier-is-the-variable` | a cell's `--model` cannot be inherited; tier dominated routing (haiku 3/14 vs sonnet 8/14) |
| 4 | any phase **writes the shared tree** | matrix or in-session — **never workflow** | `writes-shared-tree` | no hook sees a Workflow dispatch's writes |
| 5 | **fan-out width is decided at runtime** | in-session | `runtime-fanout-width` | a workflow's node set is a literal |
| 6 | a deterministic script sequence, no agents | in-session | `script-sequence` | a workflow with no agents is overhead plus a filesystem restriction |
| 7 | node set **fixed**, has agents, every phase **returns data** | workflow | `fixed-graph-returns-data` | the graph is the literal a workflow needs; nothing inside writes the shared tree |
| 8 | the fan-out's combined context **exceeds one session** | workflow | `context-exceeds-session` | each `agent()` holds its own context — see the token argument below |

And one row that is not a backend: **one scope, one correct answer, a deterministic check —
no fan-out at all.** N candidates buy N diffs and one decision the check already made. Say so
and hand back to `arbeitsplan-patterns`.

## The `why` vocabulary

`backend.why` is a **closed list** of the ids above; `compile_spec.py` rejects anything else. Each
id names the kinds it can justify, and a `why` that selects a different kind than `backend.kind`
is rejected — so `{"kind": "workflow", "why": ["does-it-fire"]}` does not compile. Several ids may
apply; list every one that does.

## What the compiler refuses

- `why` empty, or an id outside the vocabulary — a free-text reason is a label, not a decision.
- `kind: "workflow"` with any phase declaring `writes: "shared"`. Under the workflow backend a
  candidate writes in its own worktree and returns its diff **as data**; `land_candidate.py`
  applies it afterwards, in-session, where the hook and its `writeScope` check both run.
- `kind: "workflow"` without `"workflow-tool-unhooked"` in `acknowledgedGaps`.
- `kind: "matrix"` with any phase carrying `agentType` — a cell is not a dispatch.

## The unhooked gap

No `PreToolUse` matcher in this repository names the Workflow tool, and both guards'
`DISPATCH_TOOLS` are `Skill`, `Task`, `Agent`. So launching a workflow is invisible to
`arbeitsplan_guard.py`, and nothing attributes its inner dispatches to the run's budget.
Whether the **inner** subagents' own `Write`/`Edit` calls reach the hook is unmeasured: one
matrix cell (~$0.35) would settle it. Until it is measured, the compiler closes the dangerous
combination instead — no shared-tree writer under `workflow` — and the acknowledgement makes
choosing it a stated decision rather than an unnoticed one.

## The token argument, recorded as `reasoned`

The case for `workflow` beyond rows 1–7 was put by the user and is recorded as reasoning, not
measurement. Each parallel agent holds its own context, so a fan-out processes far more tokens
than one session can (on the order of ~1M in one session versus 15M+ across agents). And N
agents each given one angle are less biased than one model topic-hopping through a single
context, where the first framing anchors the rest. Both are plausible and unmeasured here;
cite them as `reasoned`, never as a rate.
