# Changelog

All notable changes to the `cupertino` plugin are documented here.

## [Unreleased]
### Added
- **`cupertino-repair`** (orchestrator skill + `references/design-sources.md`): change an existing system
  (dashboard, page, CLI, library, build, kernel) with six operations -- read, verify, modify, add, create,
  delete -- via objective, baseline, approved changeset, scoped apply, verify. New scripts
  `preflight_repair.py`, `repair_state.py`, `baseline.py`, `probes.py` (web / command / file),
  `apply_delete.py` (reversible), `verify.py`, `design_sources.py`, `repair_lib.py` and
  `build_repair_html.py`, with `assets/repair-viewer.html`, its screenshot and a committed demo
  (`scripts/fixtures/repair-demo.json`).
- **Guard scope for repair runs** (`hooks/pretooluse_guard.py`): while a run is active every
  `Write`/`Edit`/`MultiEdit`/`NotebookEdit` is limited to the active approved item's paths, shell writes and
  deletes and git mutations are denied, gate files are script-only, and `cupertino-council`/`-elevate`/
  `-unbox`/`-reveal` are denied. `hooks/test_repair_guard.py` asserts it denies and allows.
- **Behavioural cases** `cupertino-dashboard-repair` and `cupertino-cli-repair` in `test/plugins/cases.tsv`, with
  `test/plugins/calibrate-cupertino-oracles.sh`. Not yet run live: the cloud box they were written on is not
  an isolated clean box.
- `cupertino-council` writes `.cupertino/flags/council-done`; `beats.json` now names that marker as evidence.
### Changed
- **Report viewer on the shared report kit** (`tools/report-kit/`, vendored into `scripts/` and `assets/` via `.rrt.toml` `artifact_targets`): every finding carries its evidence, with filters, search, deep links, light and dark themes and drill-down. The viewer builder and report data are unchanged; its committed screenshot is regenerated with `scripts/ci/capture_viewer_screenshot.py`.
- **BREAKING -- first-use denial.** The guard used to be inert in a repo with no `.cupertino/` directory and so
  allowed `cupertino-focus`, `-longevity`, `-integrate` and `-council` on first use, defeating the
  backwards-first gate. It now denies them there, and the reason points at `cupertino-repair` for changing
  an existing system. Run `cupertino-backwards` first, or set `CUPERTINO_DISABLE_GUARD=1`.
- **BREAKING -- handbook check summary schema.** Each finding now requires `rule` and `quotedLine`; check
  summaries written before this change fail validation and must be regenerated with `cupertino-handbook-check`.
- **Handbook route made safe**: `cupertino-handbook-fix` acts on analyzed-only rules by default, runs the
  remediator on sonnet with one location per dispatch, relocates by quoted text instead of line number, and
  runs a before/after test command, so working code is no longer rewritten to invented rules.
- The `cupertino-council`, `-review`, `-elevate`, `-unbox` and `-reveal` descriptions, and `befund-ui-audit`'s,
  now route "fix an existing X" to `cupertino-repair`.
- **README**: new Example Prompts entry, a section on the repair route, components, enforcement table and
  verification commands updated.

## [1.2.0] - 2026-10-30
### Changed
- **README**: opens with the purpose block (#144) -- a one-sentence thesis, `**The name.**`, a
  `Use when` / `Not when` pair naming the sibling plugin to use instead, and a `## Use case`
  with a real call and a verbatim excerpt of committed output.
- **`plugin.json` description**: now the README thesis, word for word, and synced to
  `marketplace.json`.

## [1.1.0] - 2026-10-21

### Added
- **judge-contract**: one LLM-as-judge contract across plugins (#119) (#137)
- **ci**: the floor lint requires every registered hook to self-check (#123) (#133)

### Fixed
- **nacharbeit,arbeitsplan**: an omitted or caller-supplied model inherits by design (#118) (#136)
- **ci**: auto-version-bump survives merges that land seconds apart (#135)
- **zeugnis**: both guards deny below Python 3.11 (#131)
- **befund**: guard denies below Python 3.11 (#130)
- **lehre**: guard denies below Python 3.11 (#129)
- **andon**: guard denies below Python 3.11 (#128)
- **nacharbeit**: guard denies below Python 3.11 (#127)
- **takt**: guard denies below Python 3.11 (#126)
- **matrize**: guard denies below Python 3.11 (#125)
- **cupertino**: guard denies below Python 3.11 instead of crashing open (#124)
- **zeugnis**: Bash guard no longer crashes open under Python 3.9 (#121)
- **nacharbeit**: calibrated review and fix pass run outside werkstoff (#117) (#120)
- **lehre**: close the three agentic-reliability gaps in #96
- gate auto-version-bump on the call input (#27); recognise spec-listed CSS/Sass at-rules (#29) (#108)
- **plugins**: run every skill-invoked plugin script with python3 -B, plugin root quoted (#88 follow-up) (#104)
- every workflow agent() names its tier; dispatches brief relayed requests (#87, #90) (#101)
- **arbeitsplan**: measured checks, preserving sweep, reason-reading breaker (#81, #76, #80, #78, #93) (#100)
- **arbeitsplan**: compile_spec validates what it used to count (#77, #74, #75, #79) (#99)
- **andon**: evidence can go stale (#72); worktrees share the main ledger (#71) (#98)
- close three fail-open paths in andon, and the two cleanups underneath (#97)
- stop three guards denying beyond their own rule (#95)
- **andon**: keep wire degradation on a strategy whose trigger fired (#94)

## [1.0.4] - 2026-10-20
### Fixed
- **hook**: `hooks/pretooluse_guard.py` raised `TypeError` at import under Python 3.9 (the
  module-level `Exception | None` annotation), exited 1 -- which Claude Code treats as
  non-blocking -- and so allowed every call in a repo with `.cupertino/`. It now imports on old
  interpreters (`from __future__ import annotations`) and, past the inert check, denies below
  `MIN_PYTHON = (3, 11)` with the interpreter named and the escape hatch (#123).
### Added
- **`hooks/test_pretooluse_guard.py`**: runs the guard under every python3 older than 3.11 on
  PATH -- active repo denied, inert repo allowed, and a sabotaged copy with the floor lowered
  allowed, so the version check is proven to be what denies. Wired into CI with uv's 3.9/3.10
  and `REQUIRE_OLD_PYTHON=1`, so a missing interpreter fails instead of skipping.

## [1.0.3] - 2026-09-27
### Fixed
- **symbol index**: CSS, SCSS, Sass and Less at-rules outside the old six (`@container`, `@page`,
  `@property`, `@scope`, `@mixin`, `@include`, `@use`, ...) were recorded as `selector` symbols, and
  statement at-rules (`@charset "...";`, `@use '...';`) not at all. The vendored
  `scripts/build_symbol_index.py` now recognises exactly the at-rules MDN's at-rules reference and
  sass-lang.com's at-rules pages list (fetched 2026-09-27), Sass ones only in `.scss`/`.sass`, and a
  Less `@variable:` is still not an at-rule (#29).

## [1.0.2] - 2026-09-26
### Fixed
- **skills**: every `python3 "${CLAUDE_PLUGIN_ROOT}/…"` that a skill, command or
  workflow tells the model to run now carries `-B` (frontmatter `allowed-tools`
  patterns updated to match), so a script importing a sibling no longer writes
  `__pycache__` into the installed plugin cache copy (#88 follow-up)
- **hooks**: run the PreToolUse command with `python3 -B` so importing a sibling script
  (e.g. `pretooluse_guard.py` -> `scripts/validators.py`) no longer writes `__pycache__`
  into the installed plugin cache copy (#88)

## [1.0.1] - 2026-09-26

### Fixed
- every workflow agent() names its tier; dispatches brief relayed requests (#87, #90) (#101)
- **arbeitsplan**: measured checks, preserving sweep, reason-reading breaker (#81, #76, #80, #78, #93) (#100)
- **arbeitsplan**: compile_spec validates what it used to count (#77, #74, #75, #79) (#99)
- **andon**: evidence can go stale (#72); worktrees share the main ledger (#71) (#98)
- close three fail-open paths in andon, and the two cleanups underneath (#97)
- stop three guards denying beyond their own rule (#95)
- **andon**: keep wire degradation on a strategy whose trigger fired (#94)

## [1.0.0] - 2026-09-21

_No notable changes recorded._

## [0.10.0] - 2026-09-12

### Added
- **arbeitsplan**: a twelfth plugin that compiles a problem into a swarm — and the dead workflow it exposed (#60)
- **matrize**: an eleventh plugin that derives a design system from exemplars (#59)
- **nacharbeit**: a tenth plugin that reworks a plugin to the Anthropic standard (#58)

### Fixed
- **ci**: install PyYAML in auto-version-bump.yml (#57)
- **ci**: checkout repo and scope changelog extraction to workspace root in github-release job

## [0.9.1] - 2026-09-09

### Fixed
- **ci**: install PyYAML in auto-version-bump.yml (#57)
- **ci**: checkout repo and scope changelog extraction to workspace root in github-release job

## [0.9.0] - 2026-09-07

### Added
- **lehre**: a ninth plugin that enforces a researched code doctrine at the tool-call layer (#51)
- task-indexed prompt catalog, takt sequencing hook, and a VitePress docs site (#43)
- vendor a real D3 subset for self-assess stage-map and cli-scaffold architecture tree
- pipeline topology + drill-down for andon, review-flow diagram for cupertino
- add architecture-tree HTML viewer to every cli-scaffold paradigm
- add HTML board for andon and pass-history burndown for confab
- add codebase-consistency plugin (#34)
- enforce conventional branch naming via rrt (#31)
- **symbol-indexer**: extract real symbols from CSS, HTML, and Markdown/MDX (#28)
- cluster same-file findings, add symbol-graph safety check, extend CI with plugin checks
- **ci**: attach CHANGELOG.md section to GitHub releases (#8)
- **cupertino**: add self-contained handbook lifecycle (design/code/testing/docs) (#7)
- **self-assess**: reporting→plan bridge + cross-plugin auto-pilot (#6)

### Fixed
- **test**: derive docs-audit exclusions from config.mjs srcExclude (#54)
- **ci**: publish plugin releases from CI instead of relying on the tag push (#53)
- **docs**: fix favicon/logo node clearance and mark color (#49)
- **ci**: plugin-release and auto-version-bump missing takt group (#46)
- honest no-data state and real drill-down/search across all HTML viewers
- remove dead symbol-indexer copy from cli-scaffold, wire it into compass-explore-branches
- **self-assess**: scope guard_target_edit.py to an edit-scope lock, not repo-wide (#40)
- auto-version-bump's workflow_call input path was dead code (#37)
- auto-version-bump and plugin-release missing codebase-consistency group (#36)
- derive vendored-copy test's plugin set from .rrt.toml, not directory scan (#35)
- **compass**: normalize stringified args in workflow scripts (#30)
- **self-assess**: commit orphaned frontmatter.py in scripts/lib/
- **self-assess,confab**: restore missing scripts/lib/ packages, stop guard hooks denying every edit (#24) (#26)
- **cli-scaffold**: correct version drift and bump to v0.2.1 (#18)
- **andon**: correct version drift and bump to v0.3.1 (#17)
- **self-assess**: list ui-audit in dashboard empty-state hint (#9)
- **ci**: write the SBOM to tools/werkstoff-cli so the upload step finds it

### Documentation
- homepage redesign, agent-voice fix, and nav reorder (#55)
- add a docs UX test suite and implement the reading-rhythm design system (#48)
- fix catalog rendering and resolve doc-vs-doc contradictions (#50)
- pairing-indexed reference, homepage plugin list, and design fixes (#45)
- rebuild the prompt catalog, add a surface index, and fix two documented-vs-real drifts (#44)
- expand Example Prompts across six plugin READMEs
- correct polluted changelog entries for the 2026-08-01 release (#38)

## [0.8.0] - 2026-09-05

### Added
- **lehre**: a ninth plugin that enforces a researched code doctrine at the tool-call layer (#51)
- task-indexed prompt catalog, takt sequencing hook, and a VitePress docs site (#43)
- vendor a real D3 subset for self-assess stage-map and cli-scaffold architecture tree
- pipeline topology + drill-down for andon, review-flow diagram for cupertino
- add architecture-tree HTML viewer to every cli-scaffold paradigm
- add HTML board for andon and pass-history burndown for confab
- add codebase-consistency plugin (#34)
- enforce conventional branch naming via rrt (#31)
- **symbol-indexer**: extract real symbols from CSS, HTML, and Markdown/MDX (#28)
- cluster same-file findings, add symbol-graph safety check, extend CI with plugin checks
- **ci**: attach CHANGELOG.md section to GitHub releases (#8)
- **cupertino**: add self-contained handbook lifecycle (design/code/testing/docs) (#7)
- **self-assess**: reporting→plan bridge + cross-plugin auto-pilot (#6)

### Fixed
- **docs**: fix favicon/logo node clearance and mark color (#49)
- **ci**: plugin-release and auto-version-bump missing takt group (#46)
- honest no-data state and real drill-down/search across all HTML viewers
- remove dead symbol-indexer copy from cli-scaffold, wire it into compass-explore-branches
- **self-assess**: scope guard_target_edit.py to an edit-scope lock, not repo-wide (#40)
- auto-version-bump's workflow_call input path was dead code (#37)
- auto-version-bump and plugin-release missing codebase-consistency group (#36)
- derive vendored-copy test's plugin set from .rrt.toml, not directory scan (#35)
- **compass**: normalize stringified args in workflow scripts (#30)
- **self-assess**: commit orphaned frontmatter.py in scripts/lib/
- **self-assess,confab**: restore missing scripts/lib/ packages, stop guard hooks denying every edit (#24) (#26)
- **cli-scaffold**: correct version drift and bump to v0.2.1 (#18)
- **andon**: correct version drift and bump to v0.3.1 (#17)
- **self-assess**: list ui-audit in dashboard empty-state hint (#9)
- **ci**: write the SBOM to tools/werkstoff-cli so the upload step finds it

### Documentation
- add a docs UX test suite and implement the reading-rhythm design system (#48)
- fix catalog rendering and resolve doc-vs-doc contradictions (#50)
- pairing-indexed reference, homepage plugin list, and design fixes (#45)
- rebuild the prompt catalog, add a surface index, and fix two documented-vs-real drifts (#44)
- expand Example Prompts across six plugin READMEs
- correct polluted changelog entries for the 2026-08-01 release (#38)

## [0.7.0] - 2026-09-03

### Added
- **lehre**: a ninth plugin that enforces a researched code doctrine at the tool-call layer (#51)
- task-indexed prompt catalog, takt sequencing hook, and a VitePress docs site (#43)
- vendor a real D3 subset for self-assess stage-map and cli-scaffold architecture tree
- pipeline topology + drill-down for andon, review-flow diagram for cupertino
- add architecture-tree HTML viewer to every cli-scaffold paradigm
- add HTML board for andon and pass-history burndown for confab
- add codebase-consistency plugin (#34)
- enforce conventional branch naming via rrt (#31)
- **symbol-indexer**: extract real symbols from CSS, HTML, and Markdown/MDX (#28)
- cluster same-file findings, add symbol-graph safety check, extend CI with plugin checks
- **ci**: attach CHANGELOG.md section to GitHub releases (#8)
- **cupertino**: add self-contained handbook lifecycle (design/code/testing/docs) (#7)
- **self-assess**: reporting→plan bridge + cross-plugin auto-pilot (#6)

### Fixed
- **docs**: fix favicon/logo node clearance and mark color (#49)
- **ci**: plugin-release and auto-version-bump missing takt group (#46)
- honest no-data state and real drill-down/search across all HTML viewers
- remove dead symbol-indexer copy from cli-scaffold, wire it into compass-explore-branches
- **self-assess**: scope guard_target_edit.py to an edit-scope lock, not repo-wide (#40)
- auto-version-bump's workflow_call input path was dead code (#37)
- auto-version-bump and plugin-release missing codebase-consistency group (#36)
- derive vendored-copy test's plugin set from .rrt.toml, not directory scan (#35)
- **compass**: normalize stringified args in workflow scripts (#30)
- **self-assess**: commit orphaned frontmatter.py in scripts/lib/
- **self-assess,confab**: restore missing scripts/lib/ packages, stop guard hooks denying every edit (#24) (#26)
- **cli-scaffold**: correct version drift and bump to v0.2.1 (#18)
- **andon**: correct version drift and bump to v0.3.1 (#17)
- **self-assess**: list ui-audit in dashboard empty-state hint (#9)
- **ci**: write the SBOM to tools/werkstoff-cli so the upload step finds it

### Documentation
- add a docs UX test suite and implement the reading-rhythm design system (#48)
- fix catalog rendering and resolve doc-vs-doc contradictions (#50)
- pairing-indexed reference, homepage plugin list, and design fixes (#45)
- rebuild the prompt catalog, add a surface index, and fix two documented-vs-real drifts (#44)
- expand Example Prompts across six plugin READMEs
- correct polluted changelog entries for the 2026-08-01 release (#38)

## [0.6.0] - 2026-08-04

### Added
- vendor a real D3 subset for self-assess stage-map and cli-scaffold architecture tree
- pipeline topology + drill-down for andon, review-flow diagram for cupertino
- add architecture-tree HTML viewer to every cli-scaffold paradigm
- add HTML board for andon and pass-history burndown for confab
- add codebase-consistency plugin (#34)
- enforce conventional branch naming via rrt (#31)
- **symbol-indexer**: extract real symbols from CSS, HTML, and Markdown/MDX (#28)
- cluster same-file findings, add symbol-graph safety check, extend CI with plugin checks
- **ci**: attach CHANGELOG.md section to GitHub releases (#8)
- **cupertino**: add self-contained handbook lifecycle (design/code/testing/docs) (#7)
- **self-assess**: reporting→plan bridge + cross-plugin auto-pilot (#6)

### Fixed
- honest no-data state and real drill-down/search across all HTML viewers
- remove dead symbol-indexer copy from cli-scaffold, wire it into compass-explore-branches
- **self-assess**: scope guard_target_edit.py to an edit-scope lock, not repo-wide (#40)
- auto-version-bump's workflow_call input path was dead code (#37)
- auto-version-bump and plugin-release missing codebase-consistency group (#36)
- derive vendored-copy test's plugin set from .rrt.toml, not directory scan (#35)
- **compass**: normalize stringified args in workflow scripts (#30)
- **self-assess**: commit orphaned frontmatter.py in scripts/lib/
- **self-assess,confab**: restore missing scripts/lib/ packages, stop guard hooks denying every edit (#24) (#26)
- **cli-scaffold**: correct version drift and bump to v0.2.1 (#18)
- **andon**: correct version drift and bump to v0.3.1 (#17)
- **self-assess**: list ui-audit in dashboard empty-state hint (#9)
- **ci**: write the SBOM to tools/werkstoff-cli so the upload step finds it

### Documentation
- expand Example Prompts across six plugin READMEs
- correct polluted changelog entries for the 2026-08-01 release (#38)

## [0.5.0] - 2026-08-03

### Added
- pipeline topology + drill-down for andon, review-flow diagram for cupertino
- add architecture-tree HTML viewer to every cli-scaffold paradigm
- add HTML board for andon and pass-history burndown for confab
- add codebase-consistency plugin (#34)
- enforce conventional branch naming via rrt (#31)
- **symbol-indexer**: extract real symbols from CSS, HTML, and Markdown/MDX (#28)
- cluster same-file findings, add symbol-graph safety check, extend CI with plugin checks
- **ci**: attach CHANGELOG.md section to GitHub releases (#8)
- **cupertino**: add self-contained handbook lifecycle (design/code/testing/docs) (#7)
- **self-assess**: reporting→plan bridge + cross-plugin auto-pilot (#6)

### Fixed
- remove dead symbol-indexer copy from cli-scaffold, wire it into compass-explore-branches
- **self-assess**: scope guard_target_edit.py to an edit-scope lock, not repo-wide (#40)
- auto-version-bump's workflow_call input path was dead code (#37)
- auto-version-bump and plugin-release missing codebase-consistency group (#36)
- derive vendored-copy test's plugin set from .rrt.toml, not directory scan (#35)
- **compass**: normalize stringified args in workflow scripts (#30)
- **self-assess**: commit orphaned frontmatter.py in scripts/lib/
- **self-assess,confab**: restore missing scripts/lib/ packages, stop guard hooks denying every edit (#24) (#26)
- **cli-scaffold**: correct version drift and bump to v0.2.1 (#18)
- **andon**: correct version drift and bump to v0.3.1 (#17)
- **self-assess**: list ui-audit in dashboard empty-state hint (#9)
- **ci**: write the SBOM to tools/werkstoff-cli so the upload step finds it

### Documentation
- expand Example Prompts across six plugin READMEs
- correct polluted changelog entries for the 2026-08-01 release (#38)

## [0.4.1] - 2026-08-01

### Added
- `cupertino-review` threads prior stage content forward via a persistent state mechanism (`state.py` + tests), so every stage sees prior stages' actual content before dispatching the next one; state clears at run start/end so a stale flag from an unrelated prior review can't be mistaken for this run's progress (#32)

### Changed
- README: add a "Why this exists" section ahead of mechanism (#33)

## [0.4.0] - 2026-07-31

### Added
- **symbol-indexer**: extract real symbols from CSS, HTML, and Markdown/MDX (#28)
- cluster same-file findings, add symbol-graph safety check, extend CI with plugin checks
- **ci**: attach CHANGELOG.md section to GitHub releases (#8)
- **cupertino**: add self-contained handbook lifecycle (design/code/testing/docs) (#7)
- **self-assess**: reporting→plan bridge + cross-plugin auto-pilot (#6)

### Fixed
- **self-assess**: commit orphaned frontmatter.py in scripts/lib/
- **self-assess,confab**: restore missing scripts/lib/ packages, stop guard hooks denying every edit (#24) (#26)
- **cli-scaffold**: correct version drift and bump to v0.2.1 (#18)
- **andon**: correct version drift and bump to v0.3.1 (#17)
- **self-assess**: list ui-audit in dashboard empty-state hint (#9)
- **ci**: write the SBOM to tools/werkstoff-cli so the upload step finds it

## [0.3.2] - 2026-07-29

### Added
- cluster same-file findings, add symbol-graph safety check, extend CI with plugin checks
- **ci**: attach CHANGELOG.md section to GitHub releases (#8)
- **cupertino**: add self-contained handbook lifecycle (design/code/testing/docs) (#7)
- **self-assess**: reporting→plan bridge + cross-plugin auto-pilot (#6)

### Fixed
- **self-assess**: commit orphaned frontmatter.py in scripts/lib/
- **self-assess,confab**: restore missing scripts/lib/ packages, stop guard hooks denying every edit (#24) (#26)
- **cli-scaffold**: correct version drift and bump to v0.2.1 (#18)
- **andon**: correct version drift and bump to v0.3.1 (#17)
- **self-assess**: list ui-audit in dashboard empty-state hint (#9)
- **ci**: write the SBOM to tools/werkstoff-cli so the upload step finds it

## [0.3.1] - 2026-07-28

### Fixed
- Corrected `plugin.json`'s version, which had regressed to `0.1.0` when this
  plugin was rebuilt from its behavior specification (repo commit `0c10fa0`),
  silently overwriting the real version already published as
  `cupertino-v0.3.0` on 2026-07-25. No functional or content change beyond
  this correction.

### Added
- README: new `## Example Prompts` section with real, verified prompt-to-skill
  examples; new `## Skills`/`## Agents` top-level headings (previously only
  prose bullets under `## Components`), with descriptions pulled from each
  skill/agent's own frontmatter; `## Design decisions` heading wording
  unified with the other five plugins (#14).

## [0.1.0] - 2026-07-27

### Added

- Initial release. Generated from a behavior specification extracted from the
  prior hand-written implementation, via `tools/plugin-serializer/` and the
  official `/plugin-dev:create-plugin` path — a clean-room rebuild rather than
  a port, so none of the previous wording carried over.
