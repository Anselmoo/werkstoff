---
name: self-assess-autopilot
description: This skill should be used when the user asks to "run the auto-pilot", "check, plan, fix and validate this repo", or wants the full self-assess value stream run end to end. Conducts CHECK (read-only findings) -> PLAN (modernization brief) -> a hard approval gate -> FIX+VALIDATE (handed to andon-loop), halting on any unproven wire or unmet blocker.
version: 0.1.0
---

# self-assess-autopilot

Run self-assess's full check -> plan -> fix -> validate value stream.

## Step 0: Settings gate

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/self_assess_cli.py check-enabled --repo <repo_root> --skill self-assess-autopilot
```

## Step 1: CHECK phase -- stage-map first, then everything else in parallel

Rule `autopilot-stage-map-fresh-reuse`: **before** invoking `self-assess:self-assess-stage-map`,
check whether its outputs can be reused instead of rebuilt:

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/self_assess_cli.py stage-map-fresh-check --repo <repo_root>
```

- If `fresh` is `true`, **skip invoking `self-assess:self-assess-stage-map`** — its
  `stage_graph.json` and `file_stage_index.json` already exist and are not stale relative to the
  latest commit. Tell the user you're reusing the existing stage map rather than silently
  redoing it, and proceed straight to dispatching the other finding domains.
- If `fresh` is `false`, invoke `self-assess:self-assess-stage-map` — either it has never run,
  a prior run left it incomplete, or the repo has changed since it last ran. This is also true
  the first time autopilot ever runs in a repo (nothing to reuse yet).

Rule `autopilot-stage-map-first` (unchanged): whichever branch above applies, stage-map's
outputs (fresh or reused) MUST be settled before any other finding domain starts — it writes
`stage_graph.json` and `file_stage_index.json`, which `self-assess-arch-health` and
`self-assess-transform-brief` both require. Do not parallelize stage-map with the rest.

Once stage-map's outputs are settled, dispatch the remaining finding domains in parallel:
`self-assess-docs-drift`, `self-assess-ci-topology`, `self-assess-lint-audit`,
`self-assess-code-idiom`, `self-assess-extract-rules`, `self-assess-arch-health`,
`self-assess-complexity-score`, `self-assess-ui-audit`.

Rule `autopilot-confab-optional`: attempt to invoke confab's audit skills (e.g.
`confab:confab-cycle`) only if the confab plugin is actually installed in this session (it
will appear in the available-skills listing). If it does not appear, report "confab not
installed" plainly and continue -- never fabricate confab-shaped findings to fill the gap.

Rule `autopilot-check-phase-read-only`: every skill in this phase only reads and produces
findings. Do not use Edit, and do not use Write for anything other than each skill's own
declared output artifacts.

## Step 2: PLAN phase

Dispatch `self-assess:self-assess-transform-brief` to synthesize every CHECK-phase artifact
into `MODERNIZATION_BRIEF.md`.

## Step 3: Gate before FIX -- a persisted approval, not a remembered question

Rule `autopilot-gate-before-fix`: present `MODERNIZATION_BRIEF.md` to the user and ask them to
approve running the fix phase, either for all phases or phase-by-phase. Approval must be
recorded in `.claude/self-assess.local.md` as `autopilot.fix_approved: true` (optionally
`autopilot.approved_phases: [...]` to scope it) before proceeding. Check it in code, do not
rely on remembering the conversation said yes:

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/self_assess_cli.py autopilot-fix-gate --repo <repo_root>
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
