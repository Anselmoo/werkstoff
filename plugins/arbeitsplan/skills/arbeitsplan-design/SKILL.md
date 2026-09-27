---
name: arbeitsplan-design
description: Designs a workflow node by node before anything runs — for each step, what it does, where it runs (primary checkout, agent worktree, scratch directory), when (dependencies, human gates between runs) and how (kind, model, write scope, output schema, and for script nodes the exact command and its toolchain, in any language). Use when the user wants to plan a workflow step by step, a restructuring spans several waves, a deterministic step (a gate, a conformance runner, a state helper) would otherwise be disguised as an agent, or a hand-written workflow keeps making where/when/how decisions in prose. Read-only; produces a validated design.json and a handoff, never runs it.
argument-hint: "<the approved problem statement, or its path>"
---

# Design a workflow, node by node

`arbeitsplan-compile` picks a pattern per phase. This skill answers the questions compile
leaves in prose, **before** anything runs. For every node it asks:

- **what** the node does;
- **where** it runs;
- **when** it runs;
- **how** it runs.

A hand-written multi-wave prototype answered them ad hoc. Three of its bugs came from that: a
wrong worktree base, state passed as a JSON string, and a gate run where untracked files live.

Run this skill in **plan mode**. It writes nothing but the design under `analysis/arbeitsplan/`,
and only after the user approves.

## Steps

1. **Read the contract first.** `references/design-table-schema.md` defines every key and
   every rejection. `references/patterns.md` has `script-step` and `gated-disjoint-waves`, and
   explains why a merge of *unproven* partitions is still rejected.

2. **Take an approved problem statement, not a vague one.** If it is not scoped, stop and scope
   it (`zirkel:zirkel-clarify-scope` when zirkel is installed; ask directly when it is not, and
   say so). Record its path as `problemRef`.

3. **Snapshot the agent types that exist now**, before designing anything:

   ```bash
   python3 -B "${CLAUDE_PLUGIN_ROOT}/scripts/handoff.py" snapshot --root . \
     --out analysis/arbeitsplan/<runId>/agents-before.json
   ```

   The handoff compares against this snapshot. An agent type added in the middle of a session
   does not resolve in `agent()`.

4. **Find the repository's own toolchain before writing a single command.** Read its build
   files: `Makefile`, `go.mod`, `Cargo.toml`, `*.csproj`, `package.json`, `*.cabal`,
   `pyproject.toml`, `Project.toml`, `build.gradle`, `CMakeLists.txt`, or whatever is there.
   Write the gates, acceptance and smoke steps in **that** toolchain. Never write `pytest`
   into a project that does not use it. If a runtime is not among the built-ins, declare it
   under `toolchains`.

5. **Walk the nodes one at a time.** For each, settle with the user:

   | question | the node's keys |
   |---|---|
   | what | `goal`, `output_schema` (strict, no JSON-in-a-string) |
   | where | `where`: `primary`, `worktree` or `scratch` |
   | when | `depends_on`; a `human-gate` only *between* runs |
   | how | `kind`, `model` (always explicit), `agentType`, `writeScope`, `inputs` (ids and paths only), `script` or steps |

   A deterministic step — a gate, a conformance runner, a state helper — is a `script` node.
   It is **not** an agent told to run a command. When the repository has no such command yet,
   the node **authors** it: `script.author = {model, purpose, sample}` in a wave design, in
   bash, pwsh, ruby, node or python, following the repository's own language where it can (see
   the schema's "Authored steps"). The plan writes the script and verifies it before anything
   runs it.

6. **Prove the write scopes.** Dispatch `arbeitsplan:scope-prover` for the rows that run
   concurrently. Where two rows need one shared file (a module manifest, a lockfile), give it
   to one owner: an integrator row that depends on both, or a scaffold row in an earlier wave.

7. **Validate, without writing:**

   ```bash
   python3 -B "${CLAUDE_PLUGIN_ROOT}/scripts/compile_spec.py" --design \
     --spec analysis/arbeitsplan/<runId>/design.draft.json
   ```

   Every `REJECTED` line names its key. Fix the design, never the validator.

8. **Preflight the toolchains.** The compile prints one `TOOLCHAIN <name> <probe>` line per
   runtime the design names. Invoke `arbeitsplan-preflight`, which runs each probe; exit 0
   means installed. A missing toolchain makes the design **not ready**, however clean it
   compiled.

9. **Render the design as a graph** for the user to approve from. Record the probes' results
   as `{toolchain: true|false}` in `analysis/arbeitsplan/<runId>/preflight.json`, then:

   ```bash
   python3 -B "${CLAUDE_PLUGIN_ROOT}/scripts/build_design_html.py" \
     --design analysis/arbeitsplan/<runId>/design.draft.json \
     --preflight analysis/arbeitsplan/<runId>/preflight.json \
     --out analysis/arbeitsplan/<runId>/design-report.html
   ```

   It prints the page's verdict. The page shows which rows run side by side, any two that may
   write the same file, and where a human gate ends a run. Every rejection on it comes from the
   same validator as step 7.

10. **Present the design table and the preflight results**, in the output format below, and
   ask for approval. Approval binds to the printed sha256. When an ExitPlanMode hook is
   available, it can check that hash, but that binding is unprobed, so say so rather than
   claim it.

11. **On approval**, write the design:

    ```bash
    python3 -B "${CLAUDE_PLUGIN_ROOT}/scripts/compile_spec.py" --design --write \
      --spec analysis/arbeitsplan/<runId>/design.draft.json
    ```

    Then hand off:

    ```bash
    python3 -B "${CLAUDE_PLUGIN_ROOT}/scripts/handoff.py" plan \
      --design analysis/arbeitsplan/<runId>/design.json \
      --snapshot analysis/arbeitsplan/<runId>/agents-before.json
    ```

## Execute, then hand off

- **Execute** in auto mode, from the **primary checkout**:
  - a design with waves goes to `arbeitsplan-waves`;
  - a single change goes to `arbeitsplan-compile` and then `arbeitsplan-run`, with each script
    node becoming a `script` phase.

  The run stops at the first checkpoint or red gate and leaves a state file to resume from.
- **Same session:** `EnterWorktree` into the branch the run produced. The cwd, settings and
  CLAUDE.md move with it; agents and hooks are read from the main checkout.
- **A later turn:** when the design created agent types, `handoff.py` says
  `LAUNCH IN A LATER TURN`. A type written mid-session is not found in the turn that wrote it,
  and resolves from the next turn on. A fresh session with the exact start prompt
  `handoff.py plan` prints also works.

What `scripts/probe_runtime.py` measured on CLI 2.1.283 (ADR 0004), beyond the docs:

- **Plan mode holds inside a worktree the same way it holds in the primary checkout.** Asked
  to write a file in plan mode, the model declined in both, 3 of 3 each. That is the model
  honouring the mode; a headless run never reached the harness's own refusal, so do not treat
  a worktree as a way around plan mode, nor as a second lock.
- **Resume returns to the worktree.** A session that ran `EnterWorktree`, resumed from the
  primary checkout, starts in that worktree and remembers the conversation, 3 of 3.
- **Agent types: a later turn, not a new session** (above), 3 of 3 for both the Agent tool and
  a Workflow `agent()`.

## Rules

- **Never infer a gating value.** A node without a model is refused, and so is a wave design
  without `integration.target`. The skill *proposes* a default (opus for builders and
  referees, sonnet for merger, smoke, reviewer and fixer, haiku for script runners); the
  design *states* it.
- **Commands come from the repository, not from habit.** Every example here is one language
  among many. Match the project.
- **A human gate is between runs.** A Workflow run cannot pause for input, and the validator
  refuses a gate that does not cut the graph in two.
- **Writes nothing before approval**, and never runs the design.

## Output format

```
design rebuild-cli (run ap-2026-09-27-wv01)  sha256 3f9c1e…  — compiles clean
problem: analysis/arbeitsplan/ap-2026-09-27-wv01/problem.md

 node        kind        where     when (after)        model   writes             command / check
 preflight   script      primary   —                   haiku   —                  python3 …_state.py preflight
 w1-parse    agent       worktree  preflight           opus    internal/parse/**  go test ./internal/parse/...
 w1-render   agent       worktree  preflight           opus    internal/render/** go test ./internal/render/...
 gate-1      merge-gate  primary   w1-parse, w1-render haiku   —                  gates: go vet, go test
 w2-cli      agent       worktree  gate-1              opus    cmd/tool/**        go test ./cmd/tool/...
 gate-2      merge-gate  primary   w2-cli              haiku   —                  gates: go vet, go test
 smoke       agent       scratch   gate-2              sonnet  —                  go build …; go run … --help
 review      agent       primary   smoke               sonnet  —                  —
 fix         agent       worktree  review (if blocking) sonnet internal/**, cmd/** —

toolchains: go (go version) — installed · python (python3 --version) — installed, helper >= 3.10
integration: waves merge into integration/rebuild-cli; main moves only on a green gate
new agent types: rebuild-cli-builder, -smoke, -reviewer, -fixer, -runner → LAUNCH IN A LATER TURN than the install
Approve this design (sha256 3f9c1e…)?  Next: arbeitsplan-waves install, then launch on the next turn.
```

## Resources

- `references/design-table-schema.md` — every key, every rejection, and the two worked
  fixtures (Go, and Rust with an integrator row).
- `references/patterns.md` — `script-step`, `gated-disjoint-waves`, and the rejected
  `partition-then-merge-worktrees` this narrows.
- `scripts/handoff.py` — the snapshot, and the new-session prompt when one is required.
- `scripts/build_design_html.py` — the design (and later its run) as a graph with a verdict;
  `assets/design-viewer.html` is its template.
