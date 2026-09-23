# Changelog

All notable changes to the `arbeitsplan` plugin are documented here.

## [Unreleased]

### Added
- **stacked fan-outs: `base`, `AP-SIBLING-INVISIBLE`, and `--strict` (#79)**: a `fanout-redundant`
  phase may now declare `base: "<phaseId>"`, naming an earlier `fanout-redundant` phase whose
  refereed winner its own worktrees should start from — a fan-out is redundancy over ONE scope
  in isolated worktrees made from HEAD, so a later wave's builders otherwise never see an earlier
  wave's landed work unless it was promoted. `base` is valid only when it names an earlier
  `fanout-redundant` phase that some earlier `fanout-blind` phase actually reviewed and this
  phase's own `requires` transitively reach — anything else is `AP-BASE-INVALID`; any `base` at
  all under `backend.kind: "workflow"` is `AP-BASE-BACKEND` (`run.js`'s `isolation: "worktree"`
  cannot honour it). A new `WARNING`, `AP-SIBLING-INVISIBLE`, fires when a `fanout-redundant`
  phase's transitive `requires` reach another `fanout-redundant` phase (walked over the marker →
  producing-phase map, stopping at any `writes: "shared"` phase on the way) that its `base` chain
  does not also reach — naming both phases, printed whether or not the spec is also rejected for
  something else. A plain compile still writes on a warning (exit 0); the new `--strict` flag
  turns any warning into a rejection (exit 1). `worktree_pool.py` gained `create --phase P` (seeds
  every worktree from `arbeitsplan/<runId>/base/<Q>` when `P` declares `base: Q`, refusing by
  name if that branch was never promoted), `promote --run R --phase Q --candidate cW` (commits a
  candidate worktree, untracked files included, and points `arbeitsplan/R/base/Q` at it), and
  `destroy --run R --bases` (also deletes every `arbeitsplan/R/base/*` branch — without it they
  survive for a later wave). All three rule ids join `RED_RULES` as recorded-red, each with a
  committed fixture under `scripts/fixtures/red/` proven by `scripts/test_red_fixtures.py`.
- **`breaker` is now validated (#75)**: `compile_spec.py` never checked a phase's `breaker`
  object, so a permanently disabled gate (`workflows/run.js`'s comparisons compare `scoped *
  acceptDenominator < measured * acceptNumerator`) compiled clean. A new `validate_breaker`
  helper rejects: `acceptNumerator`/`acceptDenominator` missing, not an object, or not a plain
  int (a `bool` is not an int here) — `AP-BREAKER-INCOMPLETE`; `acceptNumerator == 0`, which
  makes the comparison `x < 0` and never trips — `AP-BREAKER-DISABLED`; a ratio outside
  `1 <= acceptNumerator <= acceptDenominator` — `AP-BREAKER-RATIO`; a `scope` present and not
  exactly `"per-batch"` — `AP-BREAKER-SCOPE`; and a `breaker` declared on a phase whose kind is
  not one of the three fan-out kinds, including `single-writer` and `referee-fixture` (nothing
  reads it there) — `AP-BREAKER-KIND`. All five join `RED_RULES` as recorded-red, each with a
  committed fixture under `scripts/fixtures/red/` proven by `scripts/test_red_fixtures.py`.
  `workflows/run.js`'s `DEFAULT_BREAKER` ({2, 3}) already satisfies the same bound.
- **phase `outputs`, `--dry-land` and `--probe-checks` (#74)**: any phase may now declare
  `outputs`, the paths it is expected to produce, checked at compile time with no flag needed
  against the same two tests `land_candidate.py` applies at landing (imported, never
  re-derived): outside `writeScope` is `AP-OUTPUT-OUTSIDE-SCOPE`; inside `refereeOwned` on a
  fan-out phase is `AP-OUTPUT-REFOWNED`; a `referee-fixture` phase's `outputs` must still equal
  `refereeOwned` exactly (wave 1's rule, unchanged). `--dry-land` prints `DRYLAND <phaseId>
  <path> IN|OUTSIDE|REFOWNED` per declared output and compiles as normal. `--probe-checks`
  (opt-in — a plain compile executes nothing) runs every `problem.acceptance[].check` once via
  the shell, cwd the process's own, under `--probe-timeout` (default 60s), printing `PROBE
  <acceptanceId> <CLASS> exit=<n>`; any check that does not classify `RAN` is rejected,
  `AP-CHECK-NOT-RAN`. All three ids join `RED_RULES` as recorded-red, each with a committed
  fixture under `scripts/fixtures/red/` proven by `scripts/test_red_fixtures.py`.
- **`referee-fixture` phase kind and `refereeOwned` (#77)**: a spec can now declare paths a
  single-writer fixture phase produces before any candidate exists, and that are subtracted
  from every fan-out phase's effective write scope. `land_candidate.py` refuses (citing
  `refereeOwned` by name) any candidate diff that touches one; `worktree_pool.py open` narrows
  a fan-out phase's lock scope by the same subtraction, computed once in
  `land_candidate.subtract_referee_owned` and shared by both call sites. New
  `scripts/referee_owned.py` hashes each path at creation (`record`, refused a second time for
  the same run or against a path that does not exist yet) and re-checks it by content
  (`verify`), so a candidate that reached one anyway is detected rather than assumed impossible.
- **Recorded-red validators**: `compile_spec.py`'s new `RED_RULES` dict names, per rule id, the
  issue that motivated a validator rejecting a spec HEAD `3f62503` compiled clean.
  `AP-REFOWNED-NO-PRODUCER` and `AP-REFOWNED-OUTSIDE-SCOPE` are the first two. Every fixture
  under `scripts/fixtures/red/` is proven both halves of that claim by new
  `scripts/test_red_fixtures.py`, which `compile_spec.py --selftest` now calls directly, and
  which CI now runs alongside `compile_spec.py --selftest`, `land_candidate.py --selftest` and
  `worktree_pool.py selftest`.

### Fixed
- **`emit_beats.py` scopes every phase beat to the phase in flight**, using takt's new
  `when`: the lock `worktree_pool.py open` writes must hold the beat's `runId` and `phase`.
  Beats were matched by agent name alone, which caused two failures once
  `.claude/takt.local.md` was live:
  - Stacked waves sharing `candidate-builder` denied wave 1 on wave 2's marker, so run
    `ap-2026-09-22-6cb2` had to leave takt off.
  - Every phase beat also listed `arbeitsplan-run`, so the skill was denied until every
    phase's marker existed. No run could start.

  The selftest now runs a two-wave spec through the real takt guard, phase by phase.
  Removing `when` turns it red.
- **`land_candidate.py` no longer reports a false `divergedFrom` for created files**: the
  landing record compared the candidate's hunks with a post-apply `git diff`, which cannot see
  a file `git apply` just created (it is untracked), so every added line came back as
  `onlyRecorded`. Run `ap-2026-09-22-6cb2` landed 16 new files byte-identically and still
  recorded a divergence. New `applied_diff()` diffs untracked paths against `/dev/null` with
  `--no-index` (the index is never touched); a selftest lands a file-creating diff in a
  throwaway repo and asserts no divergence, and asserts a real post-apply edit is still recorded.

## [1.0.0] - 2026-09-21

_No notable changes recorded._

## [0.3.1] - 2026-09-20

### Changed
- **agents**: dropped the duplicated `Typical triggers include ...` sentence and the
  `See "When to invoke" in the agent body ...` pointer from the agent descriptions
  (all 11 agents). A `description` is loaded into every session; the body is loaded only
  on dispatch. The removed prose already sits verbatim in each file's own
  `## When to invoke` section, so the corpus paid for it permanently and bought
  nothing. What tells agents apart is untouched: the job, hard scope constraints and
  every negative boundary. 7564 -> 4720 description characters, no agent body
  changed.

## [0.3.0] - 2026-09-19
### Added
- **schema v2**: `backend` is an object `{kind, why[], acknowledgedGaps[]}` with a closed
  `why` vocabulary; every phase requires `mode`, `writes` and a namespaced `agentType`;
  `fanout-readonly`, `sources`, `reDerive`, `borrowGate` and `cannotCheck`; 12-phase cap.
  `schemaVersion: "1"` is refused by name with the migration in the message.
- **`arbeitsplan-backend`** skill and `references/backend-selection.md`: matrix vs workflow
  vs in-session, first-match decision table, the unhooked-Workflow gap made explicit.
- **`workflows/run.js`** executes `spec.phases` generically, halts before every plan-mode
  phase (`pending_plan_node`), enforces the dispatch budget in code, and returns span-shaped
  events. `scripts/test_run_workflow.js` runs it against stub hooks, sabotaged nine ways.
- Seven agents: `inventory-extractor`, `contract-author`, `synthesizer`, `implementer`,
  `refactorer`, `cleaner` (proposes only), `adjudicator`. `implementer`/`refactorer` must
  answer five forgotten-work keys, checked in `run.js`.
- **The run directory is the plan of record**: `run.jsonl` via the shared
  `tools/run-record/run_record.py`; `record_event.py`, `reconcile.py`, `sample_rederive.py`,
  `sweep_artifacts.py`, `check_contract_sync.py`; `landed.json` with `divergedFrom`.
- A `Stop` hook that refuses one completion while an armed phase is unrecorded.
- **arbeitsplan**: a front door that recommends and nothing else
- **arbeitsplan**: isolated testing the matrix can prove
- **arbeitsplan**: a twelfth plugin that compiles a problem into a swarm — and the dead workflow it exposed (#60)
- **matrize**: an eleventh plugin that derives a design system from exemplars (#59)
- **nacharbeit**: a tenth plugin that reworks a plugin to the Anthropic standard (#58)

### Changed
- `worktree_pool.py open` refuses a plan-mode phase; `close` refuses a phase with no terminal
  event (`--halt "<reason>"` records one). The guard's plan-file denial names the way out.
- Python ≥ 3.11 is declared and checked in both hooks and the record library.

### Fixed
- `emit_beats.py` doubled the agent namespace (`arbeitsplan:arbeitsplan:…`), emitting beats no
  dispatch could match.
- `run.js` defaulted a missing `modelTier` to `sonnet`, inventing a gating value.
- `run_matrix.sh --dry-run` created an empty output directory under `analysis/`.
- The guard used `datetime.UTC` (3.11+) while claiming to run on any python3; under 3.9 it
  denied delegation with a bare traceback.
- **ci**: install PyYAML in auto-version-bump.yml (#57)
- **ci**: checkout repo and scope changelog extraction to workspace root in github-release job

### Documentation
- harmonize the docs and enforce the corporate design tokens (#61)

## [0.2.0] - 2026-09-12
### Changed
- converted to `pathlib.Path` throughout (41 modernization findings to **zero**), together with
  `B904` cause-chaining, two dead `# noqa` directives that suppressed nothing, and
  `datetime.UTC`. `os.path.normpath` and `os.path.relpath` are **kept deliberately** in
  `arbeitsplan_guard.py` with the reason in a comment: `Path` has no lexical `normpath` (only
  `.resolve()`, which touches the filesystem and follows symlinks — a behaviour change inside a
  write-scope check), and `Path.relative_to` raises where `relpath` returns `../outside` unless
  `walk_up=True`, which is 3.12+. A hook runs under whatever `python3` the machine has, and a
  hook that cannot import denies every call
- all four guard sabotage checks were re-run after the refactor; 8, 1, 3 and 4 cases go red
  respectively, confirming the change did not make any test vacuous

### Fixed
- **The two beats round 2 compiled were both wrong, and one was harmful.** `andon requires
  transform-brief-written` duplicated `andon_core.py:check_ingest_prereqs`, which already
  enforced it in code and better — both artifacts, `isfile`, and only when
  `gap_source == "self-assess-brief"`. The beat fired *unconditionally*, so it denied
  `andon-loop` in its **default** `gap_source: self-scan` mode, which needs no brief at all,
  escapable only by `TAKT_DISABLE_GUARD=1` — which disables every other beat too. Removed.
  `arbeitsplan requires branches-explored` removed as well: optional, and its evidence lives at
  a run-scoped UUID path no fixed `require` can name
- the round-2 audit that produced that beat classified cross-plugin references by **keyword over
  SKILL.md prose** and never opened a script. A rule enforced in code reads, to a prose scanner,
  exactly like a rule enforced by nothing

### Added — beats schema v2, so those mistakes cannot be made again
- **`evidence` is required on every `produces`.** `kind: "artifact" | "receipt" | "none"`.
  `none` is **legal to declare and impossible to depend on**: the compiler refuses any beat
  requiring it and quotes the recorded `why`, so the step stays in the registry with its reason
  instead of being re-derived by someone shipping the same unwritable marker. Of eleven declared
  produces, **seven are `none`** — most steps in this repo leave nothing durable behind
- **`alreadyEnforcedBy`** on a `requires`: the compiler refuses to compile a duplicate of an
  existing in-code enforcement. Two enforcements of one rule is drift waiting to happen, and the
  second is usually the weaker
- a beat with artifact evidence now gates on **the real produced path** with
  `requireKind: "file"`, not on a marker something must remember to touch
- `--repo-only` compiles **zero** beats today and says so explicitly — that is a result, not an
  error, and it writes nothing rather than making takt live for no gain

### Notes
- sabotage-tested: remove the `alreadyEnforcedBy` refusal and the harmful beat reappears;
  remove the `kind: none` refusal and an unsatisfiable beat compiles. Both cases go red

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
