# Changelog

All notable changes to the `takt` plugin are documented here.

## [Unreleased]

### Fixed
- `takt_guard.py` read only `tool_input["file_path"]`, so a `MultiEdit` carrying its
  paths in an `edits` array produced no target, matched no beat, and was **allowed** in
  a repository that had opted in — a silent bypass of a fail-closed guard. Every path a
  payload exposes (`file_path`, `edits[].file_path`, `file_paths`) is now collected, a
  beat is violated if any of them is gated, and a payload with no determinable path at
  all is denied rather than allowed
- `test/plugins/verify-takt-payload-shapes.py` pins the payload shapes the shared
  `verify-hooks-deny.py` harness cannot express, and runs in CI
- two further holes of the same class, found while re-auditing that fix: a `file_paths`
  value supplied as a *string* was iterated character-by-character, filling the target
  set with junk so the fail-closed branch never fired; and a `Skill`/`Task`/`Agent`
  dispatch whose name could not be determined was allowed by a beat that gates
  dispatches. Both now deny

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
