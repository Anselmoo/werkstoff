# Changelog

## [Unreleased]

## [0.1.1] - 2026-07-28

### Added
- cluster same-file findings, add symbol-graph safety check, extend CI with plugin checks
- **ci**: attach CHANGELOG.md section to GitHub releases (#8)
- **cupertino**: add self-contained handbook lifecycle (design/code/testing/docs) (#7)
- **self-assess**: reporting→plan bridge + cross-plugin auto-pilot (#6)

### Fixed
- **self-assess**: list ui-audit in dashboard empty-state hint (#9)
- **ci**: write the SBOM to tools/werkstoff-cli so the upload step finds it


All notable changes to the `andon` plugin are documented here.

## [0.1.0] - 2026-07-27

### Added

- Initial release. Generated from a behavior specification extracted from the
  prior hand-written implementation, via `tools/plugin-serializer/` and the
  official `/plugin-dev:create-plugin` path — a clean-room rebuild rather than
  a port, so none of the previous wording carried over.
