# Changelog

All notable changes to the `arbeitsplan` plugin are documented here.

## [Unreleased]
### Added
- **`scripts/rounds.py`: a shared hole or a moving residual, from ONE derived record (#78,
  #93)**: the NO CANDIDATE ACCEPTED halt is arithmetic and never looks at WHY a batch failed,
  so a structural hole every candidate shares routed straight back into widening -- which cannot
  fix a hole nothing candidate-shaped can close (#78); and a per-batch breaker only ever looks
  at ONE round, so a run that "advances, not closes" every round, each time naming a NEW
  blocking condition, passed it forever (#93). `rounds.py record --run <runId>` rebuilds one
  "round" per referee phase -- even when two referee phases in one run reuse candidate ids
  c1/c2, previously silently dropped because `record_event.py` wrote `referee/<id>.json`
  write-once and never a second time; it now ALSO writes `referee/<phase>/<id>.json`,
  write-once per (phase, id), so a second phase's verdicts are recorded rather than skipped --
  across a run and everything it `supersedes` (a new optional top-level spec key), oldest run
  first. `rounds.py decide --rounds FILE [--max-advancing-rounds N] [--spec workflow.json]`
  reads those rounds and prints exactly one `ROUTE ` line: `ROUTE SYNTHESIZE criterion=<id>`
  when the latest round accepted no one and >= 2 rejections share an unmet criterion;
  `ROUTE HALT moving-residual` when the last N JUDGED rounds are all `"advanced"` with non-null,
  pairwise-distinct `judge.blocking` ids (N from `--max-advancing-rounds`, else the spec's new
  `roundBreaker.maxAdvancingRounds`, else 3) -- and wins any tie with `SYNTHESIZE`; otherwise
  `ROUTE CONTINUE`. `workflows/run.js`'s no-accept halt now carries `rejectionsByCriterion`
  and names `rounds.py decide` in its `abortReason`; its single-writer phase, given no refereed
  winner and `carry.sharedHole = {criterion, candidates: [{candidateId, diff}]}`, renders every
  rejected candidate's diff and the missing criterion -- so synthesis is reachable from a halt
  by relaunching at that phase, not just from a refereed winner. `compile_spec.py` validates the
  two new top-level keys: `supersedes` (a non-empty runId string, never this spec's own --
  `AP-SUPERSEDES-INVALID`, recorded-red) and `roundBreaker.maxAdvancingRounds` (a plain `int >=
  2` -- `AP-ROUNDBREAKER-INVALID`, recorded-red), both HEAD (e42621b) silently ignored as
  unrecognised top-level keys. The adjudicator now returns `round: {outcome, blocking}` and is
  told to REUSE an earlier round's `blocking` id when the same obstacle recurs, which is what
  keeps a genuinely repeated blocker from looking like N different ones to `decide`.
- **pre-land measurement gate (#76)**: `reconcile.py --run-checks` measured, but nothing in
  the operator's path RAN it before landing -- a builder's self-reported exit codes were
  trusted straight through to `land_candidate.py --apply`. `reconcile.py` gains
  `--candidate CID --tree DIR`, run from the MAIN repository root: it executes every checked
  criterion of the run's acceptance (`phases/contract.json` over `workflow.json`, same
  precedence as always) with `cwd=DIR` -- the CANDIDATE's own worktree, never the main tree --
  and appends one `execute_tool` event per check to the run's `run.jsonl`, each carrying
  `detail.candidate == CID`. It then compares that measurement against the candidate's own
  `candidates/CID.json` report, GROUPED BY CRITERION ID ONLY -- never by the builder's own
  command spelling -- and prints `CONTRADICTION <id>: ...` (exit 1) for any disagreement in
  EITHER direction; for an array check, an all-zero report where one element actually fails is
  a contradiction, and a truthful per-element report is not. A criterion the builder never
  reported at all carries no claim and is NEVER a contradiction -- it still needs its own
  measurement, or it stays unmeasured. `land_candidate.contradicts()` is the one comparator
  both this gate and `land_candidate.py`'s landing gate call, so they cannot diverge (amended
  after the adjudicator found w3-c1's land gate keyed the report by exact `(id, command)` and
  treated an unreported criterion as `None != exit`, i.e. contradicted forever; w2g is the
  regression criterion). `land_candidate.py
  --apply` now REFUSES a candidate lacking its OWN measurement (`detail.candidate` must equal
  that candidate -- another candidate's measurement never unlocks it) for any checked
  criterion, or whose latest measurement contradicts its report, naming `reconcile.py` and
  `--run-checks` as the remedy; an honestly-reported failure a referee already accepted is
  NOT blocked by this gate. Every refusal `land_candidate.py` makes -- not just this new one --
  is now RECORDED in `run.jsonl` as an `execute_tool land_candidate` event, status `refuted`,
  `node_id` the candidate (previously only an accepted landing was recorded).
  `arbeitsplan-run`'s `## Steps` and `## The workflow backend` sections, and `workflows/run.js`'s
  completion return, all name the measure step.
- **`kept/<runId>-<cid>` preserves dirty losers before deletion (#80)**: `sweep_artifacts.py`
  removed a finished run's worktrees with `git worktree remove --force` -- destroying a
  rejected candidate's uncommitted work outright -- and never deleted the throwaway
  `arbeitsplan/<runId>/<cid>` branches at all; `worktree_pool.py destroy` had the same
  force-remove problem. Both now share ONE helper, `worktree_pool.preserve_then_remove` --
  the only place under `scripts/` that calls `git worktree remove`. A DIRTY worktree (tracked
  changes, or untracked non-ignored files) is committed in full and `kept/<runId>-<cid>` is
  pointed at that commit BEFORE the worktree is removed; a clean worktree gets no `kept/`
  branch. FAIL CLOSED: if preservation cannot write (e.g. a read-only object store), that
  worktree and its `arbeitsplan/<runId>/<cid>` branch are left exactly in place and
  `sweep_artifacts.py --apply` exits 1. `sweep_artifacts.py`'s existing properties are
  unchanged -- dry run by default (and now names, per dirty worktree, the `kept/` branch it
  would create and every candidate branch it would delete, without touching anything), a run
  that has not ended keeps its worktrees and branches and gets no `kept/`, and a proposal only
  narrows. `worktree_pool.py destroy` keeps its `--keep` and `--bases` semantics unchanged.
  Documented in `skills/arbeitsplan-run/SKILL.md`'s "delete the losers" step and in the README.

### Fixed
- **the sweep and `destroy` find every worktree, whatever it is named (#80)**: both selected
  candidate worktrees with `glob("c*")`, so a worktree under `.arbeitsplan/<runId>/` that
  `create` did not name was never preserved -- `sweep_artifacts.py` `rmtree`'d it with its
  parent, losing its dirty state and leaving its git metadata and branch dangling. Both now
  enumerate `git worktree list --porcelain` (`worktree_pool.worktrees_under`, which refuses
  rather than guesses when git cannot list), preserve each one through
  `preserve_then_remove`, and delete its ACTUAL branch only when it is this run's candidate
  branch -- a user's branch or a base branch is left alone. CI now runs every
  arbeitsplan selftest (`test_run_workflow.js`, reconcile, sweep, record_event, rounds), not
  only the compiler, landing and pool ones.
- **the round rules fire on in-session runs too (#78, #93)**: `rounds.py` rebuilds rounds from
  `referee/<phase>/<id>.json`, which only `record_event.py workflow` wrote -- so an in-session
  run, whose verdicts were recorded as flat `referee/<id>.json`, had no rounds at all and neither
  `ROUTE SYNTHESIZE` nor `ROUTE HALT moving-residual` could ever fire (run ap-2026-09-25-6f6f:
  three referee phases, `rounds.py record` -> `[]`). `record_event.py referee --run <runId>
  --phase <id> --verdict FILE` records an in-session batch exactly as `workflow` records a
  returned one: the flat record `land_candidate.py` reads plus the phase twin. It validates the
  whole batch before writing anything and refuses an unopened phase, a malformed verdict, a
  (phase, candidate) already recorded, and a run that has ended. Its run.jsonl event carries a
  summary (verdict, unmet ids, the record's path), not the full perCriterion, which on a
  34-criterion verdict outgrew run_record's 4096-byte atomic line. `arbeitsplan-run` step 6
  records every referee batch with it.
- **a run can end, so the sweep can collect it**: nothing in arbeitsplan ever wrote an end
  marker -- `run_record.finish()` and `refuse()` were called only by selftests -- so every
  landed or halted run read as unfinished forever, and `sweep_artifacts.py`, which removes only
  runs whose record says they ended, could never collect a real one. `record_event.py finish
  --run <runId>` ends a run through `run_record`: `complete.json` when `landed.json` exists
  (refused while a phase is open), `FAILED-<stamp>.json` carrying the halt's reason when a halt is
  recorded, refused otherwise. `record_event.py status` names it as the next command, and
  `arbeitsplan-run` makes it the last step (step 11) on both paths.
- **`landed.json` no longer reports a divergence that did not happen**: `landing_record` hashed
  the recorded and applied hunks as one ordered list, but `applied_diff()` appends the files a
  candidate created after every tracked one while the recorded diff interleaves them
  alphabetically. Any landing that created a file was flagged `divergedFrom` with empty
  `onlyRecorded`/`onlyApplied` lists (run ap-2026-09-25-6f6f: 4 created files, 2032 identical
  lines). Hunks are now compared per file -- order within a file still counts -- and
  `divergedFrom` names the differing `paths`.
- **acceptance checks render as a fenced block, and `check` accepts an array (#81)**:
  `workflows/run.js` used to render every acceptance check inline, trailing the criterion
  text inside a parenthesised clause on the same line as the id and prose -- e.g. a line
  reading `- [a1] the suite passes (check: pytest -q tests/test_x.py)`, with the command
  copied verbatim from inside that clause and told to run it. A model copying the line
  copied the trailing close-paren too, which silently changed the exit code the breaker
  acted on. Every render site -- the builder prompt, the referee prompt's acceptance
  criteria AND its separate list of checks the builder reported, and the single-writer
  prompt -- now puts each command on a line of its own, indented inside a fenced block,
  never sharing a line with any other text. `check` on an acceptance criterion is now
  `string | string[] | null`: a non-empty array runs every element independently via
  `/bin/sh`, and the criterion is met only when every element exits 0; an array's elements
  report under their criterion's own id, never a manufactured sub-id. The same normalizer
  (`land_candidate.checks_of`, mirrored in `run.js` as `checksOf`) is now imported by
  `compile_spec.py` (validation and `--probe-checks`) and `reconcile.py`'s `measure()`, so
  every reader of `check` agrees on what it means. A shape none of the three legal forms --
  a number, an object, an empty string, an empty list, or a list holding a non-string or
  empty-string element -- is rejected at compile time as `AP-CHECK-SHAPE`, a new recorded-red
  rule (`RED_RULES["AP-CHECK-SHAPE"] = 81`), proven against a committed fixture under
  `scripts/fixtures/red/` that compiled clean at HEAD (`e42621b`, which never looked at
  `check`'s type at all) and is rejected by name here. `test_run_workflow.js` gained a case
  asserting the fenced-block shape at every render site and a sabotage that reverts the
  rendering to sharing a line with the criterion text, turning the suite red.

## [1.0.1] - 2026-09-23
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
