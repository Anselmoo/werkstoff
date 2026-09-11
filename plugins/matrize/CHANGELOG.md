# Changelog

All notable changes to the `matrize` plugin are documented here.

## [Unreleased]
### Changed
- renamed from `vorbild` to `matrize` — the die a form is struck from, which is the
  architecture rather than a metaphor for it, and which sits in the same shop-floor
  register as `werkstoff`, `andon`, `takt`, `lehre` and `nacharbeit`
- **Design Card schema v2**: every card records its outgoing `reference -> card` and
  `card -> token` edges explicitly, each with its own grade (I8). Reconstruction by
  value-matching was tested against a real 50-declaration token file and failed twice —
  it merged `--space-1` with `--radius-sm` (both `4px`) and collapsed three roles
  aliasing one source into a single node

### Added
- `scripts/retrofit_css.py`, `scripts/emit_css.py` and `scripts/prove_retrofit.py` — the
  first formatter pair and the three-arm equivalence proof. Verified end to end on
  `tools/design-tokens/tokens.css`: 50 declarations, 10 aliases, **zero visual diff and
  structure preserved**
- a **secondary-source** case in the reliability rubric, capped at grade B and required
  to name what it `describes` — a third party's description of someone else's design
  system underwrites "one documented interpretation", never "this is what that vendor
  does"
- validator rules `V-NO-EDGE`, `V-EDGE-NO-GRADE`, `V-SECONDARY-GRADE-A` and
  `V-SECONDARY-NO-SUBJECT`, each planted in the selftest, with two negative controls
  proving they discriminate rather than blanket-reject

## [0.1.0] - 2026-09-11
### Added
- the twelve-skill pipeline: `matrize-{preflight,survey,collect,decode,name,brief,echo,spread,retrofit,emit,status,dolmetsch}`
- six read-only agents: `reference-decoder`, `decode-referee`, `lexicon-keeper`,
  `design-critic`, `token-emitter`, `fact-checker`
- a `PreToolUse` hook (`hooks/matrize_guard.py`) that denies edits under the design
  root's `references/` and denies a write to `system/tokens.json` or `out/` while a
  `spread` choice record is unanswered; inert unless the design root exists; escape
  hatch `MATRIZE_DISABLE_GUARD=1`
- DTCG `2025.10` as the source of truth, with `purpose`, `rule`, `anti-rule`,
  provenance, reliability grade and rights grade carried in `$extensions` under
  `com.werkstoff.matrize` — no extension to the spec itself
- a **rights grade** (R1/R2/R3) recorded alongside the reliability grade (A/B/C),
  because how far a value can be trusted and what may be reproduced from its source
  are orthogonal questions
- `references/principle-vocabulary.md`, the anti-copying instrument: a rule whose
  `purpose` names neither a measured property nor a named principle is a copy
