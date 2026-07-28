# Changelog

All notable changes to the `cli-scaffold` plugin are documented here.

## [Unreleased]

## [0.2.2] - 2026-07-28

### Added
- cluster same-file findings, add symbol-graph safety check, extend CI with plugin checks
- **ci**: attach CHANGELOG.md section to GitHub releases (#8)
- **cupertino**: add self-contained handbook lifecycle (design/code/testing/docs) (#7)
- **self-assess**: reporting→plan bridge + cross-plugin auto-pilot (#6)

### Fixed
- **cli-scaffold**: correct version drift and bump to v0.2.1 (#18)
- **andon**: correct version drift and bump to v0.3.1 (#17)
- **self-assess**: list ui-audit in dashboard empty-state hint (#9)
- **ci**: write the SBOM to tools/werkstoff-cli so the upload step finds it

## [0.2.1] - 2026-07-28

### Added
- README: new `## Example Prompts` section with real, verified prompt-to-skill
  examples, moved to right after `## Install`; `## Skills`/`## Agents` added
  as top-level headings with counts (previously only a directory tree);
  `## Design decisions` heading wording unified with the other five plugins (#14).

## [0.2.0] - 2026-07-28

### Fixed
- Corrected `plugin.json`'s version, which had regressed to `0.1.0` when this
  plugin was rebuilt from its behavior specification (repo commit `0c10fa0`),
  silently overwriting the real version already published as
  `cli-scaffold-v0.2.0` on 2026-07-25. No functional or content change.

## [0.1.0] - 2026-07-27

### Added

- Initial release, generated from a behavior specification via `tools/plugin-serializer/`.
