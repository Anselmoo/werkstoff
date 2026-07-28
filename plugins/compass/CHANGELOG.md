# Changelog

All notable changes to the `compass` plugin are documented here.

## [Unreleased]

## [0.2.1] - 2026-07-28

### Fixed
- Corrected `plugin.json`'s version, which had regressed to `0.1.0` when this
  plugin was rebuilt from its behavior specification (repo commit `0c10fa0`),
  silently overwriting the real version already published as
  `compass-v0.2.0` on 2026-07-25. No functional or content change beyond
  this correction.

### Added
- README: new `## Example Prompts` section with real, verified prompt-to-skill
  examples, moved to right after `## Install` (previously positioned late,
  after all architecture content); `## Skills`/`## Agents`/`## Enforcement
  layer` promoted from nested subsections to top-level headings; `## Design
  decisions` heading wording unified with the other five plugins (#14).

## [0.1.0] - 2026-07-27

### Added

- Initial release. Generated from a behavior specification extracted from the
  prior hand-written implementation, via `tools/plugin-serializer/` and the
  official `/plugin-dev:create-plugin` path — a clean-room rebuild rather than
  a port, so none of the previous wording carried over.
