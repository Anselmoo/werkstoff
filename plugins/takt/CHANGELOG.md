# Changelog

All notable changes to the `takt` plugin are documented here.

## [Unreleased]

### Added
- **`requireKind: "file" | "dir" | "any"`** on a beat, defaulting to `any` so every existing
  declaration behaves byte-identically. The guard used a plain `os.path.exists`, so
  `mkdir <path>` opened any gate — harmless while markers were empty touch-files, a one-command
  bypass once a beat gates on a real produced artifact. An unknown value denies, fail-closed
- the beat-graph viewer now renders **refusals** — requirements declared and deliberately not
  compiled, with the reason for each — and tags every produced marker with its evidence kind. Its
  beat list is the **compiler's**, imported from `arbeitsplan/scripts/emit_beats.py` rather than
  re-derived, and the selftest asserts the two counts agree: a page and a compiler that disagree
  about what is enforced is a page that lies

### Fixed
- **`/.takt/` is now gitignored.** A marker means "this step ran in *this* checkout"; committed,
  it satisfied its gate for every clone forever — failing **open**, silently, which is the
  opposite of the fail-closed stance every guard here takes. Deliberately *not* extended to
  `.cupertino/`, `.lehre/` or `.design/`, which hold durable project facts that should be shared
- `assets/beatgraph-viewer.html` + `scripts/build_beatgraph_html.py` + a committed demo
  fixture — the artifact takt has never had. Until now the only way to learn what takt was
  blocking was to trip over a denial; the page renders every declared beat, whether its marker
  exists, and which plugin produces it
- a **repo-level marker escape**: a relative `require` that already begins `.takt/` is taken
  as-is and is never namespaced by `runId`, while a bare name always is. One compiled
  declaration therefore carries both durable facts and per-run markers at once. The split falls
  along takt's existing convention (`require: ".takt/council-done"`), so no declaration written
  before `runId` existed changes meaning
- Optional top-level `runId` in `.claude/takt.local.md`. When present, every **relative**
  `require` marker resolves under `.takt/<runId>/` instead of against the repository root,
  so a marker left behind by an earlier run cannot satisfy a later run's beat. Omitting
  `runId` leaves behaviour byte-identical, which `hooks/test_takt_guard.py` pins under the
  name `BACKWARD`. `runId` becomes a path component, so it must match
  `[A-Za-z0-9._-]{1,64}` with no `..`; anything else denies rather than being sanitised
- `hooks/test_takt_guard.py` — takt was the only hook-bearing plugin in this repository
  with no guard unit test, which is very likely why the staleness above went unnoticed.
  Asserts deny **and** allow across inertness, the escape hatch, both marker regimes, the
  `runId` charset, and the exit-2-plus-JSON deny protocol. Sabotage-tested: blanking the
  `runId` resolution turns the `STALE` cases red and leaves `BACKWARD` green
- `scripts/validate_beats.py` — authoring-time validation of a declaration, with
  `--selftest` over 11 planted-defect declarations. Reports what the guard *tolerates*:
  a beat gating no paths or no skills is silently skipped at runtime, which is the
  likeliest bug in a generated declaration

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
