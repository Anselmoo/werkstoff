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

- **Handbook lifecycle** — `cupertino-handbook-draft`, `cupertino-handbook-
  apply`, `cupertino-handbook-check`, `cupertino-handbook-fix`: a second,
  self-contained discipline alongside the fixed 8-stage pipeline,
  persisting a project's actual design/code/testing/documentation
  conventions into a durable artifact (`docs/cupertino/handbooks/<domain>-
  handbook.md` by default) instead of re-deriving judgment fresh each
  time, and re-checking new/changed work against it. Domain-parameterized
  across all four domains rather than duplicated per domain.
- **4 new agents** — `handbook-dimension-analyst` (draft's finder/
  referee), `handbook-drift-auditor` (check's finder/referee),
  `handbook-remediator` (fix's Edit-capable remediator, the plugin's
  first Edit exception), `handbook-verifier` (fix's blind adversarial
  verifier — never given the remediator's own rationale, per
  `references/handbook-verification.md`).
- **2 new Workflow scripts** — `workflows/handbook-draft-scan.js` and
  `workflows/handbook-drift-scan.js`, both Find-then-adversarial-Verify,
  mirroring `self-assess`'s proven shape but entirely self-contained (no
  dependency on `self-assess`/`andon` skills, agents, or workflows).
- **`.claude/cupertino.local.md` settings file** — optional per-project
  configuration (`handbook.output_dir`, `handbook.domains`,
  `handbook.skip_verification`, `handbook.fix.mode`), documented in
  `references/handbook-settings.md` with a copy-pasteable example at
  `examples/cupertino.local.md`.
- **4 new per-domain dimension catalogs** —
  `references/handbook-design.md` (thin, points into existing
  `council-*.md`/`tokens-starter.css` material), `handbook-code.md`,
  `handbook-testing.md`, `handbook-documentation.md` (new catalogs
  grounded in Apple-engineering-craft framing).
- `cupertino-handbook-apply` is optionally consulted by `cupertino-review`
  ahead of its Council stage when a design handbook already exists —
  advisory only, the existing 8-stage pipeline table is unchanged.

## [0.1.0]

- Initial release.
