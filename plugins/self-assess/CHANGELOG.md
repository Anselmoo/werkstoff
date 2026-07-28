# Changelog

All notable changes to the `self-assess` plugin are documented here.

## [Unreleased]

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
