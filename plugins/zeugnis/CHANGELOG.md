# Changelog

All notable changes to the `zeugnis` plugin are documented here.
Releases before the rename were published as `confab`; tags under that name
are listed in `test/plugins/retired-groups.txt` and remain valid.

## [Unreleased]
### Added
- **zeugnis-mutation-harden** (#142): runs mutmut 3 on fresh `git archive` copies as background
  scripts, proves each killing test by applying its mutant, and reports score per module before
  and after with untested mutants, equivalents and unreached survivors apart. New
  `mutation-killer` agent, `mutation_harden` domain with a test-path lock, and a Mutation tab
  with hover, click and keyboard interactions in the burndown viewer.

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

## [1.0.6] - 2026-10-20
### Changed
- **hooks**: both guards, `guard_edit_scope.py` and `guard_bash_scope.py`, now declare
  `MIN_PYTHON = (3, 11)` and, past the inert check, deny below it with the interpreter named and
  the escape hatch (#123). Today both enforce correctly under 3.9 and 3.10, so this is the declared
  floor made explicit, not a crash fix: an import-time error in a hook exits 1 and is allowed, and
  the next 3.11-only construct would have opened that hole again with nothing reporting it.
  `guard_edit_scope.py` gained `from __future__ import annotations`, so it stays importable to say so.
- **tests**: each guard's suite has a `TestPythonFloor` class. Under every python3 older than 3.11 on
  PATH, an active repo is denied (and the denial names the floor), an inert repo is allowed, and a
  copy of `scripts/` with the floor lowered allows the same payload, which proves the version check
  is what denies. With no old interpreter the class skips, or fails under `REQUIRE_OLD_PYTHON=1`.

## [1.0.5] - 2026-10-20
### Fixed
- **hooks**: `guard_bash_scope.py` raised `TypeError` at import under Python 3.9 (`str | None` in
  `_matched_mutator`'s signature is evaluated at definition time before 3.10). A hook that crashes
  exits 1, which Claude Code treats as non-blocking, so on such a machine every Bash call was
  allowed. `from __future__ import annotations` restores import on 3.7+; `npm install x` now exits 2
  under 3.9 as under 3.12.

## [1.0.4] - 2026-09-27
### Fixed
- **symbol index**: CSS, SCSS, Sass and Less at-rules outside the old six (`@container`, `@page`,
  `@property`, `@scope`, `@mixin`, `@include`, `@use`, ...) were recorded as `selector` symbols, and
  statement at-rules (`@charset "...";`, `@use '...';`) not at all. The vendored
  `scripts/build_symbol_index.py` now recognises exactly the at-rules MDN's at-rules reference and
  sass-lang.com's at-rules pages list (fetched 2026-09-27), Sass ones only in `.scss`/`.sass`, and a
  Less `@variable:` is still not an at-rule (#29).

## [1.0.3] - 2026-09-26
### Fixed
- **skills**: every `python3 "${CLAUDE_PLUGIN_ROOT}/…"` that a skill, command or
  workflow tells the model to run now carries `-B` (frontmatter `allowed-tools`
  patterns updated to match), so a script importing a sibling no longer writes
  `__pycache__` into the installed plugin cache copy (#88 follow-up)
- **hooks**: run both PreToolUse commands with `python3 -B` so importing a sibling script
  (e.g. `guard_edit_scope.py`, `guard_bash_scope.py`) no longer writes `__pycache__` into
  the installed plugin cache copy (#88)

## [1.0.2] - 2026-09-22

### Fixed
- close three fail-open paths in andon, and the two cleanups underneath (#97)
- stop three guards denying beyond their own rule (#95)
- **andon**: keep wire degradation on a strategy whose trigger fired (#94)

## [1.0.1] - 2026-09-22

### Fixed
- stop three guards denying beyond their own rule (#95)
- **andon**: keep wire degradation on a strategy whose trigger fired (#94)

## [1.0.0] - 2026-09-21
### Changed
- **BREAKING: renamed from `confab` to `zeugnis`** -- a *Zeugnis* is the EN 10204 mill
  certificate, whose grades encode who stood behind the claim: 2.1 the supplier's own
  word, 3.1 their own inspector, 3.2 an independent one. That is this plugin's rule --
  no finding counts until a pass that did not produce it re-checks it. `confab` was
  short for confabulation, which names the defect but is not a shop-floor concept, so it
  failed the test `docs/glossary.md` states for every German-named plugin.
- **BREAKING: install identity changed.** `/plugin install confab@werkstoff` no longer
  resolves; use `/plugin install zeugnis@werkstoff`. There is no alias mechanism in the
  marketplace, so an existing install must be removed and re-added.
- **BREAKING: skill ids renamed** -- `confab-*` -> `zeugnis-*`, including `confab-cycle`
  -> `zeugnis-cycle`. The `confab-remediator` agent is now `zeugnis-remediator`.
- **BREAKING: on-disk state path changed** -- `analysis/confab/` -> `analysis/zeugnis/`.
  Existing state is not migrated. Note the Bash guard keys its inertness on that
  directory, so it stays inert until a run recreates it under the new name.
- Published `confab-v*` tags and their GitHub Releases are unchanged and stay reachable;
  `plugin-release.yml` keeps the retired name in its allowlist so they remain re-publishable.


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

## [0.5.1] - 2026-08-03

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

### Fixed
- `plan-next-pass` now falls back to reading each domain's standalone `*_summary.json` sidecar (same severity/findings-count priority rule) when the ledger has no findings yet, instead of always defaulting to `dependency_audit` on a fresh cycle regardless of unread findings sitting in another domain's sidecar (#32)

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
  silently overwriting the real version already published as `confab-v0.3.0`
  on 2026-07-25. No functional or content change beyond this correction.

### Added
- README: new `## Example Prompts` section with real, verified prompt-to-skill
  examples; `## Design decisions` heading wording unified with the other five
  plugins (#14).

## [0.1.0] - 2026-07-27

### Added

- Initial release. Generated from a behavior specification extracted from the
  prior hand-written implementation, via `tools/plugin-serializer/` and the
  official `/plugin-dev:create-plugin` path — a clean-room rebuild rather than
  a port, so none of the previous wording carried over.
