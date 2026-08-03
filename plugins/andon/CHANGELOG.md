# Changelog

All notable changes to the `andon` plugin are documented here.

## [Unreleased]

## [0.7.0] - 2026-08-03

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

## [0.6.0] - 2026-08-03

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

## [0.3.3] - 2026-07-29

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

## [0.3.2] - 2026-07-28

### Fixed
- Auto-triggered by this repo's `auto-version-bump.yml` workflow, which fires
  on any push to `main` whose head commit uses a `fix:`/`feat:` conventional-commit
  prefix touching this plugin's path — in this case PR #17's own "fix(andon):
  correct version drift..." merge subject. No further content change beyond
  #17; this entry replaces the workflow's auto-generated one, which
  (like #17's own predecessor) pulled in unrelated repo-wide commits due to a
  known changelog-scoping limitation in `rrt bump`.

## [0.3.1] - 2026-07-28

### Added
- README: new `## Example Prompts` section with real, verified prompt-to-skill
  examples; `## Skills`/`## Agents` promoted to top-level headings with counts;
  `## Design decisions` heading wording unified with the other five plugins (#14).

## [0.3.0] - 2026-07-28

### Fixed
- Corrected `plugin.json`'s version, which had regressed to `0.1.0` when this
  plugin was rebuilt from its behavior specification (repo commit `0c10fa0`),
  silently overwriting the real version already published as `andon-v0.3.0`
  on 2026-07-25. No functional or content change — this entry exists solely
  to keep the version number honest before the next real release.

## [0.1.0] - 2026-07-27

### Added

- Initial release. Generated from a behavior specification extracted from the
  prior hand-written implementation, via `tools/plugin-serializer/` and the
  official `/plugin-dev:create-plugin` path — a clean-room rebuild rather than
  a port, so none of the previous wording carried over.
