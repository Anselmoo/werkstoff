---
name: self-assess-arch-health
description: This skill should be used when the user asks to "find architecture deficiencies", "find god-objects or god-modules", "detect dependency cycles", "check for layering violations", or as part of self-assess-autopilot's CHECK phase. Reads the full stage_graph.json from self-assess-stage-map and finds god-modules, circular dependencies, and layering violations, verifying each against actual code.
version: 0.1.0
---

# self-assess-arch-health

Judge the real stage/wire dependency graph for structural deficiencies.

## Step 0: Settings gate, then the stage_graph prerequisite

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/self_assess_cli.py check-enabled --repo <repo_root> --skill self-assess-arch-health
```

Check whether `<output_dir>/stage_graph.json` exists. If it does not, this skill degrades to
`Ready-with-gaps` -- write a short `ARCH_HEALTH.md` and `arch_health_summary.json` (empty
`findings`, a note that `self-assess-stage-map` has not run) and stop. This is a degrade, not
an error: do not fail the skill invocation, just produce a minimal, honest artifact.

## Step 1: Read the full graph

Read `stage_graph.json` in full -- never the sampled viewer-format `stage_map.json`. Fan-in and
fan-out numbers must come from the complete graph.

## Step 2: Find deficiencies mechanically, then confirm against code

Use the graph helpers for the two structural checks that have precise definitions:

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/self_assess_cli.py find-cycles --stage-graph <path to stage_graph.json>
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/self_assess_cli.py find-god-modules --stage-graph <path to stage_graph.json>
```

`find-cycles` only returns strongly-connected components of size >= 2 (rule
`cycle-definition-in-graph`) -- a pair of stages that merely both import a shared third stage
is not a cycle, and the Tarjan-based implementation will not report it as one. `find-god-modules`
flags stages whose fan-in crosses the documented ratio-of-other-stages threshold (see README
"Design decisions" for the exact constant, since the spec leaves the numeric cutoff to this
plugin's judgment).

Dispatch `arch-health-auditor` to confirm each mechanically-flagged candidate against the
actual source before it becomes a finding -- a high-fan-in stage that is a legitimate shared
kernel (e.g. a `types`/`errors` package everything imports) is not a god-module, and the agent's
own refusal list covers exactly this case. Layering violations (a production stage importing a
test-only/fixture/example stage) have no purely structural signature in the graph alone --
confirm each one by reading the importing stage's actual role.

## Step 3: Validate and write

Unless `skip_verification` is set, every finding must carry `verified: true/false` from Step 2
before reaching here.

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/self_assess_cli.py validate-artifact --kind arch_health_summary --file <path-or-inline-json>
```

The validator rejects any `type` outside `{god-module, cycle, layering-violation}` and any
`cycle` finding whose `members` list has fewer than 2 entries.

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/self_assess_cli.py resolve-output-path --repo <repo_root> --filename ARCH_HEALTH.md
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/self_assess_cli.py resolve-output-path --repo <repo_root> --filename arch_health_summary.json
```

## Read-only constraint

Never use Write/Edit outside the resolved output paths. Never refactor, split, or merge a stage
here -- that is `self-assess-transform-brief`'s planning step and `self-assess-transform-
execute`'s (separately gated) execution step.
