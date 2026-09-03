# Changelog

All notable changes to the `lehre` plugin are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-09-02

### Added

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
