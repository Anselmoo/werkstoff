# Changelog

All notable changes to the `vorbild` plugin are documented here.

## [Unreleased]

## [0.1.0] - 2026-09-11
### Added
- the twelve-skill pipeline: `vorbild-{preflight,survey,collect,decode,name,brief,echo,spread,retrofit,emit,status,dolmetsch}`
- six read-only agents: `reference-decoder`, `decode-referee`, `lexicon-keeper`,
  `design-critic`, `token-emitter`, `fact-checker`
- a `PreToolUse` hook (`hooks/vorbild_guard.py`) that denies edits under the design
  root's `references/` and denies a write to `system/tokens.json` or `out/` while a
  `spread` choice record is unanswered; inert unless the design root exists; escape
  hatch `VORBILD_DISABLE_GUARD=1`
- DTCG `2025.10` as the source of truth, with `purpose`, `rule`, `anti-rule`,
  provenance, reliability grade and rights grade carried in `$extensions` under
  `com.werkstoff.vorbild` — no extension to the spec itself
- a **rights grade** (R1/R2/R3) recorded alongside the reliability grade (A/B/C),
  because how far a value can be trusted and what may be reproduced from its source
  are orthogonal questions
- `references/principle-vocabulary.md`, the anti-copying instrument: a rule whose
  `purpose` names neither a measured property nor a named principle is a copy
