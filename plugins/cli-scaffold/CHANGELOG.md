# Changelog

All notable changes to the `cli-scaffold` plugin are documented here.

## [Unreleased]

## [0.2.2] - 2026-07-28

### Fixed
- Auto-triggered by this repo's `auto-version-bump.yml` workflow, which fires
  on any push to `main` whose head commit uses a `fix:`/`feat:` conventional-commit
  prefix touching this plugin's path — in this case PR #18's own "fix(cli-scaffold):
  correct version drift..." merge subject. No further content change beyond
  #18; this entry replaces the workflow's auto-generated one, which
  (like #18's own predecessor) pulled in unrelated repo-wide commits due to a
  known changelog-scoping limitation in `rrt bump`.

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
