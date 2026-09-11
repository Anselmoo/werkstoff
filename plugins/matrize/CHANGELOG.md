# Changelog

All notable changes to the `matrize` plugin are documented here.

## [Unreleased]
### Changed
- the derivation-health report is now a **Ledger**: print-first, entirely static, with
  the shared threshold chart server-rendered into it — and no script, so the two XSS
  barriers a client-rendered viewer needs collapse into having no injection surface
- its builder now follows the house convention it had diverged from: a `--tokens`
  argument rather than a hardcoded path, and the tokens marker replaced by a whole
  `<style>` block rather than sitting inside one; CSP gained `base-uri` and `form-action`
- renamed from `vorbild` to `matrize` — the die a form is struck from, which is the
  architecture rather than a metaphor for it, and which sits in the same shop-floor
  register as `werkstoff`, `andon`, `takt`, `lehre` and `nacharbeit`
- **Design Card schema v2**: every card records its outgoing `reference -> card` and
  `card -> token` edges explicitly, each with its own grade (I8). Reconstruction by
  value-matching was tested against a real 50-declaration token file and failed twice —
  it merged `--space-1` with `--radius-sm` (both `4px`) and collapsed three roles
  aliasing one source into a single node

### Added
- `scripts/cvd.py` — CIEDE2000 under a Viénot-1999 dichromat simulation, calibrated
  against the published test set and corroborated to 0.01 against a figure `tokens.css`
  measured years earlier
- `scripts/redundancy.py` — finds categorical encodings carried by colour alone, checked
  at the point the category is RENDERED rather than where the colour is declared
- guard rule 3: denies colour-only encoding on a declared branded surface; inert unless
  `surfaces:` names some
- `scripts/emit_vitepress.py` — turns a theme's hand-copied literals into references,
  reporting ambiguities and orphans instead of resolving them
- `references/vocabulary/` — the domain layer, authored by the plugin's owner: one file
  per dimension (colour, grid and spacing, typography, motion, icons) plus
  `visual-asset-taxonomy.md`, the parent taxonomy. Each carries a **kind** per term
  (`token` / `derived` / `rule` / `property`) that routes it to tokens, the lexicon, or
  neither, and ends with **Decoding notes** giving the reliability grade each dimension
  actually yields from a reference
- the taxonomy's **Origin** column wired into `matrize-collect` as the bound on what can
  be promised at all — `drawn` classes get a system and seeds, never a library — and its
  three habitually-missing classes (empty state, error state, Open Graph image) wired
  into `matrize-brief` as mandatory coverage
- `emit --target provenance`: `assets/provenance-viewer.html` +
  `scripts/build_provenance_html.py` — reference → card → token, read from written edges
  only, with `--paranoid` re-deriving it by value-matching to show the disagreement
- `scripts/icons.py` — an icon *system*: grid, live area, padding and stroke all derived
  from the spacing base; four shared keylines; optical stroke; `~dark` naming; twelve
  seed icons defined as primitives so the same data renders and validates
- `scripts/gradients.py` — native DTCG `gradient` tokens whose stops are role
  *references*, each carrying the illustration anti-rule; absent gradients are reported
  as findings rather than invented
- icon and gradient spreads in the Specimen
- the **Specimen**: `assets/sketchbook-template.html` + `scripts/build_sketchbook_html.py`,
  landscape A4 at √2 measured off a real reference, with approval and handoff modes
- `scripts/chart.py` — one threshold-chart primitive, four call sites (contrast, motion,
  type scale, spacing); dot-with-stem, log axis for ratios, colour always redundant to
  position, shape and a printed value
- text-into-illustration: an over-budget note becomes a do/don't figure when it has a
  structured rule/anti-rule pair, and is flagged rather than invented when it does not
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
