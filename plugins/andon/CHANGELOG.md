# Changelog

All notable changes to this plugin will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.1] - 2026-07-23

### Added
- **ci**: attach CHANGELOG.md section to GitHub releases (#8)
- **cupertino**: add self-contained handbook lifecycle (design/code/testing/docs) (#7)
- **self-assess**: reporting→plan bridge + cross-plugin auto-pilot (#6)

### Fixed
- **self-assess**: list ui-audit in dashboard empty-state hint (#9)
- **ci**: write the SBOM to tools/werkstoff-cli so the upload step finds it

## [0.2.0] - 2026-07-21
### Added

- **`andon-loop` ingest mode (`gap_source: self-assess-brief`).** A new,
  opt-in gap source that makes `andon-loop` the **fix + validate** half of the
  cross-plugin auto-pilot: instead of self-scanning for gaps, it reads
  `self-assess`'s `MODERNIZATION_BRIEF.md`, takes the stream from the brief's
  phases, and ingests each phase's ranked work items as gaps (routed to their
  named fix skill) with the phase's Behavior Contract as the verification
  contract. Default `self-scan` behavior is unchanged; everything from Phase 3
  on (propose, the andon-rule gate, cycles) is identical. New settings:
  `gap_source` (default `self-scan`) and `self_assess_output_dir`.
- **`andon-verify` named direct-call entry point `{wire, contract, fixDiff}`.**
  Formalizes the previously-prose "when called directly" mode into a documented
  contract, so `self-assess-transform-execute` / `self-assess-idiom-fix` /
  `confab-remediator`'s hand-off to andon-verify resolves to a real andon-side
  entry (route via `wire-classifier`, prove the `fixDiff` against the
  `contract`/behavior rules, apply the andon rule) instead of an aspirational
  suggestion.

## [0.1.0]

- Initial release.
