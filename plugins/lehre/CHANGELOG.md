# Changelog

## [Unreleased]

## [0.2.0] - 2026-09-03

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
- add a docs UX test suite and implement the reading-rhythm design system (#48)
- fix catalog rendering and resolve doc-vs-doc contradictions (#50)
- pairing-indexed reference, homepage plugin list, and design fixes (#45)
- rebuild the prompt catalog, add a surface index, and fix two documented-vs-real drifts (#44)
- expand Example Prompts across six plugin READMEs
- correct polluted changelog entries for the 2026-08-01 release (#38)


All notable changes to the `lehre` plugin are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-09-02

### Added

- **Gate 0 — the guard protects its own control plane.** `lehre_guard.py` now refuses a
  write to `.lehre/units/*.done` (forging a validation marker asserts a check that never
  ran) and refuses any change to `.lehre/ruleset.json` that removes enforcement — a
  blocking rule that stops denying, or a build-order dependency edge that disappears.
  Tightening passes untouched. Both exploits were reproduced at exit 0 before the fix,
  and the six new cases in `hooks/test_lehre_guard.py` were mutation-checked: disabling
  Gate 0 makes exactly those six fail.
- The order-gate denial no longer names the marker file, which previously told a blocked
  model what to forge.

- Initial release.
- `lehre_core.py` — one shared ruleset schema and predicate evaluator, used by both the
  PreToolUse hook and the gauge CLI so a sweep and a denial cannot disagree about a rule.
- `lehre_guard.py` — `PreToolUse`, `type: "command"`. Denies a write violating a
  blocking hook-tier rule, and a write into a unit whose dependencies are unvalidated.
  Inert until `.lehre/ruleset.json` exists; fail-closed; escape hatch
  `LEHRE_DISABLE_GUARD=1`.
- `lehre_cli.py` — `validate` · `gauge` · `close` · `status`, with a frozen exit-code
  contract (0 clean · 1 sweep not clean · 2 ruleset unusable). A file that could not be
  parsed exits 1 alongside real violations: it was not judged, so reporting 0 would let
  CI record a rule as holding over a file the rule never reached.
- Nine skills covering the lifecycle: preflight, decompose, codify, gauge, brief,
  conform, validate, pin, status.
- Eight agents: spec-decomposer, doctrine-researcher, pattern-investigator, rule-critic,
  violation-auditor, violation-verifier, conformance-remediator, spec-fidelity-auditor.
- Closed check vocabulary — `forbid-path`, `require-location`, `python-import`,
  `python-construct`, `linter` — with enforcement tier derived from the kind rather than
  declared in the file.
- Provenance model (`evidence-backed` / `intent-derived` / `scaffolded-default`) with
  independent re-derivation by `rule-critic`.
- `provenance: lehre` guard on both the ruleset and `LEHRE_BRIEF.md`.
- Known-answer tests for the evaluator and behavioural tests for the hook.
- `assets/doctrine-viewer.html` + `scripts/build_doctrine_html.py` — a self-contained,
  offline doctrine map: an enforcement Sankey (ribbons coloured by terminal outcome), a
  strictly-nested funnel strip, and the unit build-order graph. Hand-written layout; the
  marketplace d3 subset carries no `d3-sankey`, so the bundle is deliberately not
  vendored. `assets/tokens.css` is vendored and registered in `.rrt.toml`.
- Four headless behavioural cases in `test/plugins/cases.tsv` with their fixtures, and
  `test/plugins/calibrate-lehre-oracles.sh` — 14 assertions proving each oracle
  discriminates against fabricated transcripts before it grades anything.
- `intent`, `owns` and `must_not_know` in the ruleset schema, so `lehre-decompose` can
  persist what `spec-fidelity-auditor` later needs instead of relying on a session's
  recollection. `lehre-validate` refuses to close a unit on rules alone when no `intent`
  is recorded, rather than treating "not checked" as "passed".
