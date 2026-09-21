---
name: befund-autopilot
description: Runs befund's full workflow (CHECK → PLAN → approval gate → FIX+VALIDATE) with andon-loop, halting on unproven wires or unmet blockers. Use when the user asks to "run the auto-pilot", "check, plan, fix and validate this repo", or wants the full befund value stream.
---

# befund-autopilot

Run befund's full check -> plan -> fix -> validate value stream.

## Step 0: Settings gate

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/befund_cli.py check-enabled --repo <repo_root> --skill befund-autopilot
```

## Step 1: CHECK phase -- stage-map first, then everything else in parallel

Rule `autopilot-stage-map-fresh-reuse`: **before** invoking `befund:befund-stage-map`,
check whether its outputs can be reused instead of rebuilt:

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/befund_cli.py stage-map-fresh-check --repo <repo_root>
```

- If `fresh` is `true`, **skip invoking `befund:befund-stage-map`** — its
  `stage_graph.json` and `file_stage_index.json` already exist and are not stale relative to the
  latest commit. Tell the user you're reusing the existing stage map rather than silently
  redoing it, and proceed straight to dispatching the other finding domains.
- If `fresh` is `false`, invoke `befund:befund-stage-map` — either it has never run,
  a prior run left it incomplete, or the repo has changed since it last ran. This is also true
  the first time autopilot ever runs in a repo (nothing to reuse yet).

Rule `autopilot-stage-map-first`: whichever branch above applies, stage-map's
outputs (fresh or reused) MUST be settled before any other finding domain starts — it writes
`stage_graph.json` and `file_stage_index.json`, which `befund-arch-health` and
`befund-transform-brief` both require. Do not parallelize stage-map with the rest.

Once stage-map's outputs are settled, dispatch the remaining finding domains in parallel:
`befund-docs-drift`, `befund-ci-topology`, `befund-lint-audit`,
`befund-code-idiom`, `befund-extract-rules`, `befund-arch-health`,
`befund-complexity-score`, `befund-ui-audit`.

Rule `autopilot-zeugnis-optional`: attempt to invoke zeugnis's audit skills (e.g.
`zeugnis:zeugnis-cycle`) only if the zeugnis plugin is actually installed in this session (it
will appear in the available-skills listing). If it does not appear, report "zeugnis not
installed" plainly and continue -- never fabricate zeugnis-shaped findings to fill the gap.

Rule `autopilot-check-phase-read-only`: every skill in this phase only reads and produces
findings. Do not use Edit, and do not use Write for anything other than each skill's own
declared output artifacts.

## Step 2: PLAN phase

Dispatch `befund:befund-transform-brief` to synthesize every CHECK-phase artifact
into `MODERNIZATION_BRIEF.md`.

## Step 3: Gate before FIX -- a persisted approval, not a remembered question

Rule `autopilot-gate-before-fix`: present `MODERNIZATION_BRIEF.md` to the user and ask them to
approve running the fix phase, either for all phases or phase-by-phase. Approval must be
recorded in `.claude/befund.local.md` as `autopilot.fix_approved: true` (optionally
`autopilot.approved_phases: [...]` to scope it) before proceeding. Check it in code, do not
rely on remembering the conversation said yes:

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/befund_cli.py autopilot-fix-gate --repo <repo_root>
```

A non-zero exit here means approval is not yet recorded -- stop at Step 3 and wait. Do not
proceed to Step 4 under any circumstance without a passing gate.

## Step 4: FIX+VALIDATE -- hand off, do not do it here

Rule `autopilot-halt-on-andon-blocker`: once the gate passes, hand FIX+VALIDATE to
`andon:andon-loop` for the approved phase(s) -- this skill does not itself edit source code. If
`andon-loop` is not installed, report plainly that the plan is ready (`MODERNIZATION_BRIEF.md`)
but FIX needs the `andon` plugin, and stop there. If `andon-loop` halts on an unproven wire, a
blast-radius ceiling, or an unmet P0 blocker, surface that halt to the user verbatim -- never
force past it, never retry it silently, never treat a halt as success.

## Read-only self-check

This skill's own read/write footprint is limited to invoking other skills and relaying their
outputs; it never calls Edit directly, and never calls Write outside forwarding a sub-skill's
own resolved output paths.
