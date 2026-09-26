# Changelog

All notable changes to this tool will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- `werkstoff doctor` (read-only) and `werkstoff prune [--apply] [--keep N]` (dry-run by
  default) for stale cached plugin versions under
  `<claude-dir>/plugins/cache/<marketplace>/<plugin>/<version>/`. Every input is
  canonicalised once at the boundary in the new `werkstoff.cache` module — the claude
  dir, each registry entry's `installPath`, and the cache scan itself all resolve
  symlinks before anything is compared — so identity is decided on resolved paths, never
  path spelling: a relative `--claude-dir`, a symlinked alias for it, or a registry key
  naming `..` all resolve to the same cache or are rejected outright. `prune` never
  removes a live directory (every scope's registry entry under
  `<plugin>@<this marketplace>` counts), an uninstalled plugin's cache, or anything
  reached through a symlinked plugin or version directory (#89)

### Security
- **prune**: fail closed per plugin, and never delete what any registry entry names. A
  land-phase review reproduced six ways the first version still removed a live install;
  each is now a calibrated test and refused: an entry with no `installPath` over a
  symlinked version directory, a relative or `~` `installPath` (resolved against the cwd),
  a live directory named under another key or marketplace, a bind-mount alias (identity is
  now `(st_dev, st_ino)`), a marketplace name of `..`, and an install that lands between
  plan and apply (`apply_prune` now re-reads the registry and re-proves each path). A
  duplicate-keyed or non-regular-file registry (a FIFO blocked forever) is refused in one
  line; `--apply --json` reports what was actually `removed`/`failed`/`skipped`; and
  pre-release tags compare numerically (`rc.10` after `rc.2`) (#89)
- **prune**: a second adversarial review reproduced more, now tested and refused: an
  installed plugin with an empty or malformed entry list, or an `installPath` naming a
  file, had its whole cache removed (it must now prove a live directory); a live
  directory nested inside a stale version, or a bind mount inside one, was removed with
  it; a plugin dir renamed or symlinked in after the check was followed (removal now goes
  through `O_NOFOLLOW` directory fds verified against the checked identities); the cache
  root is bound to its planned identity; a registry that breaks mid-apply still reports
  what was already removed; hostile registries (deep nesting, huge integers, NUL bytes,
  lone surrogates) and Rich markup in paths no longer traceback; and `--apply` re-derives
  the protected set only when the registry changed (65 s -> 0.6 s for 400 x 5,000) (#89)

## [1.0.0] - 2026-09-21

_No notable changes recorded._

## [0.2.0] - 2026-09-07

### Added
- **lehre**: a ninth plugin that enforces a researched code doctrine at the tool-call layer (#51)
- task-indexed prompt catalog, takt sequencing hook, and a VitePress docs site (#43)
- vendor a real D3 subset for self-assess stage-map and cli-scaffold architecture tree
- pipeline topology + drill-down for andon, review-flow diagram for cupertino
- add architecture-tree HTML viewer to every cli-scaffold paradigm
- add HTML board for andon and pass-history burndown for confab
- add codebase-consistency plugin (#34)
- enforce conventional branch naming via rrt (#31)
- **symbol-indexer**: extract real symbols from CSS, HTML, and Markdown/MDX (#28)
- cluster same-file findings, add symbol-graph safety check, extend CI with plugin checks
- **ci**: attach CHANGELOG.md section to GitHub releases (#8)
- **cupertino**: add self-contained handbook lifecycle (design/code/testing/docs) (#7)
- **self-assess**: reporting→plan bridge + cross-plugin auto-pilot (#6)

### Fixed
- **test**: derive docs-audit exclusions from config.mjs srcExclude (#54)
- **ci**: publish plugin releases from CI instead of relying on the tag push (#53)
- **docs**: fix favicon/logo node clearance and mark color (#49)
- **ci**: plugin-release and auto-version-bump missing takt group (#46)
- honest no-data state and real drill-down/search across all HTML viewers
- remove dead symbol-indexer copy from cli-scaffold, wire it into compass-explore-branches
- **self-assess**: scope guard_target_edit.py to an edit-scope lock, not repo-wide (#40)
- auto-version-bump's workflow_call input path was dead code (#37)
- auto-version-bump and plugin-release missing codebase-consistency group (#36)
- derive vendored-copy test's plugin set from .rrt.toml, not directory scan (#35)
- **compass**: normalize stringified args in workflow scripts (#30)
- **self-assess**: commit orphaned frontmatter.py in scripts/lib/
- **self-assess,confab**: restore missing scripts/lib/ packages, stop guard hooks denying every edit (#24) (#26)
- **cli-scaffold**: correct version drift and bump to v0.2.1 (#18)
- **andon**: correct version drift and bump to v0.3.1 (#17)
- **self-assess**: list ui-audit in dashboard empty-state hint (#9)
- **ci**: write the SBOM to tools/werkstoff-cli so the upload step finds it

### Documentation
- homepage redesign, agent-voice fix, and nav reorder (#55)
- add a docs UX test suite and implement the reading-rhythm design system (#48)
- fix catalog rendering and resolve doc-vs-doc contradictions (#50)
- pairing-indexed reference, homepage plugin list, and design fixes (#45)
- rebuild the prompt catalog, add a surface index, and fix two documented-vs-real drifts (#44)
- expand Example Prompts across six plugin READMEs
- correct polluted changelog entries for the 2026-08-01 release (#38)

## [0.1.0]

- Initial release.
