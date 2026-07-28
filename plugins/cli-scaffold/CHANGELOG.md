# Changelog

All notable changes to the `cli-scaffold` plugin are documented here.

## [Unreleased]

## [0.2.0] - 2026-07-28

### Fixed
- Corrected `plugin.json`'s version, which had regressed to `0.1.0` when this
  plugin was rebuilt from its behavior specification (repo commit `0c10fa0`),
  silently overwriting the real version already published as
  `cli-scaffold-v0.2.0` on 2026-07-25. No functional or content change.

## [0.1.0] - 2026-07-27

### Added

- Initial release, generated from a behavior specification via `tools/plugin-serializer/`.
