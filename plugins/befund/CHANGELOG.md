# Changelog

All notable changes to the `befund` plugin are documented here.
Releases before the rename were published as `self-assess`; tags under that name
are listed in `test/plugins/retired-groups.txt` and remain valid.

## [Unreleased]

### Fixed
- **hooks**: run the PreToolUse command with `python3 -B` so importing a sibling script
  (e.g. `guard_target_edit.py`) no longer writes `__pycache__` into the installed plugin
  cache copy (#88)

## [1.0.1] - 2026-09-22

### Fixed
- stop three guards denying beyond their own rule (#95)
- **andon**: keep wire degradation on a strategy whose trigger fired (#94)

## [1.0.0] - 2026-09-21
### Changed
- **BREAKING: renamed from `self-assess` to `befund`** -- a *Befund* is the written finding of an inspection: it records a condition and
  does not pass or reject the part, which is why `lehre` is the gauge and this is not.
  `docs/glossary.md` states the test this satisfies: every German-named plugin names a
  manufacturing concept its own README states. The old name did not, and a German
  spelling of it would not have either.
- **BREAKING: install identity changed.** `/plugin install self-assess@werkstoff` no longer
  resolves; use `/plugin install befund@werkstoff`. There is no alias mechanism in the
  marketplace, so an existing install must be removed and re-added.
- **BREAKING: on-disk state path changed** -- `analysis/self-assess/` -> `analysis/befund/`, `.claude/self-assess.local.md` -> `.claude/befund.local.md`. Existing state is not migrated.
- **BREAKING: skill and command ids renamed** -- `self-assess-*` -> `befund-*`.
- **BREAKING: script module names changed** -- `scripts/self_assess_cli.py` -> `scripts/befund_cli.py`.
- Published `self-assess-v*` tags and their GitHub Releases are unchanged and stay reachable;
  `plugin-release.yml` keeps the retired name in its allowlist so they remain re-publishable.

## [0.11.1] - 2026-09-20

### Changed
- **agents**: dropped the duplicated `Typical triggers include ...` sentence and the
  `See "When to invoke" in the agent body ...` pointer from the agent descriptions
  (10 of 11 agents). A `description` is loaded into every session; the body is loaded only
  on dispatch. The removed prose already sits verbatim in each file's own
  `## When to invoke` section, so the corpus paid for it permanently and bought
  nothing. What tells agents apart is untouched: the job, hard scope constraints and
  every negative boundary. 5508 -> 2475 description characters, no agent body
  changed.
- `idiom-remediator` writes `Typical trigger is ...` in the singular and carries a
  `never a batch spanning multiple files` boundary inside that sentence, so only its
  pointer sentence was removed.

## [0.11.0] - 2026-09-19
### Fixed
- `write_guard.resolve_output_path` now refuses an `output_dir` that resolves outside the repository (`..`, an absolute path). It only checked the filename against `output_dir`, and `guard_target_edit.py` allows every write inside that directory, so a hostile `output_dir` bypassed the edit gate; it now fails closed. The transform-phase record writes through the same guard, and a phase id that is not a safe path component is refused before the edit-scope lock opens.

### Added
- `open-edit-scope`/`close-edit-scope --phase N` keep `analysis/self-assess/transform-phase-<N>/run.jsonl`, which outlives the scope lock: the files the phase **actually changed**, measured with `git status`, and `--halt "<reason>"` when it stopped. `transform-execute` used to apply a phase and record nothing.

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

## [0.4.2] - 2026-08-02

### Added
- add codebase-consistency plugin (#34)
- enforce conventional branch naming via rrt (#31)
- **symbol-indexer**: extract real symbols from CSS, HTML, and Markdown/MDX (#28)
- cluster same-file findings, add symbol-graph safety check, extend CI with plugin checks
- **ci**: attach CHANGELOG.md section to GitHub releases (#8)
- **cupertino**: add self-contained handbook lifecycle (design/code/testing/docs) (#7)
- **self-assess**: reporting→plan bridge + cross-plugin auto-pilot (#6)

### Fixed
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
- correct polluted changelog entries for the 2026-08-01 release (#38)

## [0.4.1] - 2026-08-01

### Added
- `self-assess-autopilot`/`self-assess-status`: staleness tracking (`staleness.py`) and richer status reporting (`status.py`, `self_assess_cli.py`) (#32)
- Ten auditor agents plus `business-rules-miner` gained fenced worked-example output formats in place of prose-only schemas, grounded in their actual validator code (#33)
- `self-assess-extract-rules`: three-file schema/example/rendered-report split under `references/` (#33)

### Removed
- Dead `version: 0.1.0` field from all 16 `SKILL.md` files (never a real Claude Code field, never bumped since scaffolding) (#33)

### Changed
- README: add a "Why this exists" section ahead of mechanism (#33)
- Agents' `tools:` frontmatter standardized onto the documented comma-string form (#33)

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
  `self-assess-v0.3.0` on 2026-07-25. No functional or content change beyond
  this correction.

### Added
- README: new `## Install` section (previously had none) and a new
  `## Example Prompts` section with real, verified prompt-to-skill examples,
  replacing the old terse arrow-mapped `## Typical usage` table that was
  buried as the last section of the file; `## Design decisions` heading
  wording already matched the other five plugins (#14).

## [0.1.0] - 2026-07-27

### Added

- Initial release, generated from a behavior specification via `tools/plugin-serializer/`.
