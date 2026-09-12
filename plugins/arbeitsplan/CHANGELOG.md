# Changelog

All notable changes to the `arbeitsplan` plugin are documented here.

## [Unreleased]

### Added
- `references/delegation.md` and `scripts/delegation.py` — a general delegation mechanism for
  every plugin, not just compass. Append-only JSONL ledger at
  `analysis/arbeitsplan/<runId>/delegation.jsonl`, bounded by a **depth cap of 3** and
  **cycle detection**, both enforced in the `PreToolUse` hook. The two rules are not
  redundant: a cap bounds a runaway chain `A→B→C→D`, while `A→B→A` is depth 2 and sails under
  any cap. Sabotage-tested independently — unbound the cap and only the `DEPTH` cases go red;
  disable the cycle check and only `CYCLE` does
- `.claude-plugin/beats.json` in every plugin, declaring the markers each **produces** and
  **requires**. `emit_beats.py --repo-only` compiles the union into one `.claude/takt.local.md`
- `assets/run-viewer.html` + `scripts/build_run_html.py` + `scripts/fixtures/run-demo.json` —
  the run's own account of itself. The fixture carries all four outcomes deliberately, because
  a demo missing one cannot show what that state looks like

### Fixed
- `run_matrix.sh` ran a **subset** of its cells and reported a clean tally over it. `claude -p`
  inherits the cell loop's stdin and consumed the remaining list; a 2-cell sweep ran one and
  printed `PASS 1/1`. Fixed with `< /dev/null`, and pinned by a `--selftest` stub that *reads
  stdin* — the echo-only stub could not catch it, because a stub that does not exercise the
  same syscalls as the real binary is not a test of the harness
- `run_matrix.sh` refused to run whenever it detected a nested Claude Code session, on the
  strength of a measurement made in a different repository. That does not reproduce here, and
  the refusal was redundant: a cell hitting an auth banner is already `UNMEASURED` with its
  reason. Replaced by a one-call authentication probe that prints what it actually got;
  `--skip-probe` bypasses it and `--allow-nested` is kept as a deprecated alias
- the delegation cycle check compared a dispatch id (`compass:compass-solve`) against ledger
  plugin names (`compass`) and so never matched — every cycle passed. Both sides now normalize
  to the plugin prefix
- `is_cross_plugin` compared against the run's owner rather than the dispatching source, which
  classified `arbeitsplan → compass → arbeitsplan` as fan-out and skipped the cycle check on
  precisely the shape it exists for

## [0.1.0] - 2026-09-12

### Added
- **`arbeitsplan-compile`** — turns a problem in prose into `workflow.json`, a spec concrete
  enough for a machine to run and a hook to enforce. A problem that turns out to be a
  *question* rather than a *change* is refused and routed to `compass:compass-solve`, with an
  `out-of-scope-reasoning` record — the boundary is implemented, not asserted
- **`arbeitsplan-run`** — executes the spec as a redundant swarm: N candidates over the
  **same** scope in their own git worktrees, judged blind, exactly one landed, the rest
  deleted. Nothing is ever merged, so a merge conflict cannot occur
- **`arbeitsplan-matrix`** — compiles a headless `cases × models × plugin_states × repeats`
  sweep and hands the user a terminal command. It never runs the sweep: a nested `claude -p`
  cannot authenticate, and a harness that silently recorded auth failures as results would be
  worse than one that refuses
- **`arbeitsplan-patterns`**, **`arbeitsplan-preflight`**, **`arbeitsplan-status`**
- Agents `candidate-builder`, `candidate-referee`, `pattern-researcher`, `scope-prover`. The
  referee is given the acceptance criteria and a diff only — never the builder's rationale,
  angle, or any other candidate — and reports `rationaleLeaked` if that isolation is breached
- `hooks/arbeitsplan_guard.py`, a fail-closed `PreToolUse` guard denying an identical
  re-dispatch, a shared-tree write during a fan-out, a write outside `writeScope`, and a
  dispatch past the declared budget. The re-dispatch ledger is the guard's **own**: one file
  per signature created with `O_CREAT|O_EXCL`, so a repeat is the atomic create failing —
  race-free across parallel candidates, and not dependent on a skill remembering to record
  anything. Escape hatch `ARBEITSPLAN_DISABLE_GUARD=1`
- `scripts/run_matrix.sh`, a bash harness around `claude -p`. Isolation is structural —
  empty temp cwd, `--setting-sources project`, `--strict-mcp-config`, `--plugin-dir` on the
  enabled arm only — rather than an enumeration of everything currently installed
- `references/patterns.md`, a frozen catalog with a machine-readable index the compiler reads,
  carrying ten accepted patterns and five **rejected** ones with the measurement behind each
  rejection; plus `workflow-spec-schema.md`, `candidate-contract.md`, `matrix-schema.md`
- Scripts `compile_spec.py`, `emit_beats.py`, `worktree_pool.py`, `land_candidate.py`, each
  with a planted-defect `--selftest`. `emit_beats.py`'s selftest validates its own output
  with **takt's** `validate_beats.py`, so the two plugins are contract-checked against each
  other rather than separately

### Notes on what this deliberately does not do
- **Ordering.** That is `takt`'s charter — the beats span plugins, so no single plugin owns
  that order. `arbeitsplan-compile` *writes* the declaration; takt enforces it. This plugin's
  own guard covers only per-dispatch attribution, which takt structurally cannot.
- **Serial validation.** `serial-fix-loop` is in the rejected catalog by name. Convergence
  comes from widening — new independent candidates under new angles — and an identical
  re-dispatch is denied outright.
- **Reasoning.** A question is routed to `compass`, not compiled into a swarm.
