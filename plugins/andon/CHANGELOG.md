# Changelog

All notable changes to the `andon` plugin are documented here.

## [Unreleased]

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
