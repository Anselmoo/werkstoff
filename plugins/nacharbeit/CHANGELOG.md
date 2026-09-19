# Changelog

All notable changes to the `nacharbeit` plugin are documented here.

## [Unreleased]

### Added
- `Q-ROUTE-MISS` and `Q-CANN-CAPTURE`, produced in code from the routing simulation — the
  misroute it always computed and discarded is now a finding, and a handoff that still loses
  its own documented prompts to the sibling it names is no longer excused.
- `nacharbeit-probe` and `scripts/trigger_probe.py`: run a documented prompt headless in
  fresh processes and record which skill fired — fired, captured (named), silent, UNSTABLE,
  UNMEASURED — with `--routing` comparing the simulation against reality. Cells run through
  `scripts/subrun.py`, vendored from `tools/subrun/` and shared with arbeitsplan.
- `scripts/route_sim.py` runs only the review's haiku routing simulation, headless, reading
  `ROUTE_PROMPT`/`ROUTE_SCHEMA` out of `review.js` so it cannot drift; `trigger_probe.py`
  gains a `werkstoff` arm (every plugin in a clean box — the simulation's own corpus) and
  `--prompts FILE` for a sample chosen outside the prober.
- `post_fix_check.py --probe MODEL` re-measures routing-family fixes; without it the
  re-measurement is recorded as `pending` with its command.
- `status.py --fail-on-severity blocker,major` for CI (exit 1 on a match, 2 on an unknown
  severity).
- `scripts/test_review_routing.js` executes `review.js` against stub hooks and sabotages its
  routing behaviour seven ways.

### Changed
- Routing votes are awaited **before** the finders and handed to them, labelled `MEASURED`
  or `HINTS ONLY` by the 0.8 floor; only the opus pair judging stays concurrent. Below the
  floor the routing rules are recorded under `routing.rulesSkipped`, never emitted.
- Findings whose fix would make the component worse are `declined`: kept on disk, never
  backlog. Findings from a kind with no fixture pair of its own carry `calibrated: false`.
- `H-DENY-SHAPE` and `H-FAIL-CLOSED` accept a `Stop` hook's `{"decision": "block"}` and
  `block()`.

### Fixed
- `S-JS-SYNTAX` parses a workflow as the runtime does, not with `node --check`, which under
  Node's module auto-detection rejected every correct workflow.

## [0.3.0] - 2026-09-12
### Added
- `S-WF-SHAPE` (blocker) — a `workflows/*.js` file must carry a top-level `return`. The
  Workflow runtime evaluates the script *body*, so one wrapped in `export default async
  function run(...)` defines a function nothing calls and resolves to `undefined`, leaving
  every agent dispatch unreachable. It parses under `node --check` and lints clean, so
  nothing caught it until `plugins/arbeitsplan/workflows/run.js` shipped in that shape.
  Detected by parsing a copy as an ES module, where node's `Illegal return statement`
  refusal is the **positive** signal — the calibration asserts that wording still holds
  before trusting the rule, because a rename would leave it quietly passing everything
- `A-VIEWER-REQUIRED` (major) — every plugin must ship `assets/*-viewer.html`. Keyed on the
  **manifest**, because every other `A-*` rule grades a viewer that exists and so can never
  report one that does not. The rubric and the linter are checked for agreement, and the rule
  is planted in a dedicated no-viewer fixture so the calibration can sabotage it like the rest
- `assets/review-viewer.html` + `scripts/build_review_html.py` + a committed demo fixture —
  findings by severity, rule family and **fix tier**. The tier column is the point: it
  separates what a model can close from what is a judgement call, so the fixture carries a
  `human`-tier finding deliberately. The page also states that a family at `0/n` is not
  evidence of health, only that nothing exercised it

## [0.2.0] - 2026-09-09
### Added
- the instrument PR #56 built as repo-internal tooling (`tools/prompt-review/`,
  `.claude/workflows/prompt-quality-{review,fix}.js`, the rubric under `docs/`), moved
  into the plugin as its canonical home: `scripts/nacharbeit_lint.py`,
  `workflows/{review,fix}.js`, `references/rubric.md`
- five new rule families beyond the prompt-bearing `M-*`/`Q-*` set: `H-*`/`HQ-*` hooks,
  `S-*`/`SQ-*` scripts, `A-*`/`AQ-*` report viewers, `P-*`/`PQ-*` manifest, README and
  CHANGELOG, `D-*`/`DQ-*` repo-level developer docs — 90 mechanical rules, each planted
  and sabotage-tested by `scripts/test_nacharbeit_lint.py`, and 48 judgement rules
- per-family calibration: the finder must clear a recall floor for every family present
  in the sealed hold-out, not only overall, before it grades a real file of that kind
- `hooks/nacharbeit_guard.py`: a `PreToolUse` hook of `type: "command"` that, while
  `analysis/nacharbeit/fix_scope.json` is open, denies any edit outside the lock, any
  edit to an opus- or human-tier file, and any git state change; inert otherwise
- `scripts/build_fix_args.py` opens that lock and snapshots the plugins about to change;
  `scripts/post_fix_check.py` re-runs every post-check, diffs contracts against the
  snapshot, and releases the lock only when both are clean
- skills `nacharbeit-preflight`, `nacharbeit-lint`, `nacharbeit-review`,
  `nacharbeit-fix`, `nacharbeit-status`; agents `component-finder` and `fix-verifier`
  for sessions without the Workflow tool (their findings are labelled uncalibrated and
  can never reach the fix pass)
- every werkstoff-specific location is a flag with a werkstoff default, so the plugin
  runs in any repository that keeps plugins under one directory
- `test/plugins/fixtures/hook-violation-nacharbeit/`, the plugin-specific violating
  fixture `test/plugins/verify-hooks-deny.py` requires
