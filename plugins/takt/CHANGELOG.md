# Changelog

All notable changes to the `takt` plugin are documented here.

## [Unreleased]

## [0.1.0] - 2026-08-28

### Added
- `takt_guard.py`: a `PreToolUse` hook of `type: "command"` that denies an edit or a
  dispatch running ahead of a beat the repository declared it depends on
- beat declarations in `.claude/takt.local.md`, matched with `fnmatch` globs over file
  paths (`Write`/`Edit`/`MultiEdit`) or dispatch names (`Skill`/`Task`/`Agent`)
- inert-by-default behaviour: a repository without `.claude/takt.local.md` is allowed
  before the tool call is inspected, so the guard never polices an unrelated project
- fail-closed error handling once the repository has opted in, with the
  `TAKT_DISABLE_GUARD=1` escape hatch named in every denial
- `test/plugins/fixtures/hook-violation-takt/`, the plugin-specific violating fixture
  required by `test/plugins/verify-hooks-deny.py`
