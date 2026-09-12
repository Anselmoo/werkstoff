# Changelog

All notable changes to the `matrize` plugin are documented here.

## [Unreleased]

### Changed
- the Specimen speaks **English**. `build_sketchbook_html.py` hardcoded German chrome —
  `Anmerkungen`, `nicht:`, `Entscheider:`, `Freigegeben:`, `Datum:`, `Optische Grösse`,
  `Freigabe` — which shipped into *every* user's client-facing approval PDF regardless of
  their own data. The CSS class moved with it (`.anmerkungen` → `.notes-margin`, in the
  generator **and** `assets/sketchbook-template.html`, which are a matched pair), as did the
  selftest assertion coupled to the default framing string
- `scripts/fixtures/sketchbook-demo.json` translated. A translation, not a redesign: every
  structural property the renderer keys on is unchanged, verified by comparing rendered
  markers before and after — 10 spreads, 16 notes, 1 over-budget flag, 0 figures, 8 pins, 8
  observations, 15 anti-rules. The over-budget note is still over `NOTE_BUDGET` (342 chars)
  with no rule/anti-rule pair, so the flag-rather-than-draw branch stays exercised. German
  decimal commas (`3,84:1`) normalised to points, which the chart axis already used

### Fixed
- `assets/sketchbook-screenshot.jpg` was **stale**, independently of the language change: it
  showed a footer of `03 / 08` while the committed code renders `03 / 10`. Recaptured through
  the print path, and the command that produces the *image* — not just the HTML — is now in
  the README, since its absence is why nobody could diff it
- `agents/token-emitter.md`'s description listed CSS, Tailwind, SCSS, JSON and TOML without
  the "not built" qualifier every other surface carries, so it read as a capability list. It
  now says what it is: the agent that AUTHORS a formatter, including for the four targets the
  README names as absent


## [0.2.0] - 2026-09-12
### Changed
- **the vocabulary now enforces.** It reached the pipeline only as prose in four
  `SKILL.md` files, which this workshop has measured as the weakest enforcement layer
  there is — so the plugin's most load-bearing content was its least enforced.
  `scripts/vocabulary.py` compiles `references/vocabulary/` into a registry (223 dimension
  terms, 31 asset classes), `scripts/validate_tokens.py` gained thirteen rules against it,
  and guard **rule 4** refuses a write to `<root>/system/tokens.json` that contradicts it
- **Design Card schema v3**: every card names the `**Concept:**` it measured — a
  vocabulary term plus its dimension. The dimension is required because homonyms are real:
  `Opacity` is `derived` in `color-system.md` and `property` in `motion.md`, and a bare
  term naming two dimensions is refused rather than resolved to whichever parsed first
- the derivation Ledger gained a **Concepts this system names** section and a mandatory
  **appearance-mode** column on the contrast table. `color-system.md` calls a mode-less
  contrast table "the shape of the error that hides a role behaving differently in the two
  modes" — and the first version of this report's own fixture mixed `#FFFFFF` and
  `#0a0d10` backgrounds with no mode anywhere. The builder now refuses input without one
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

### Fixed
- the README claimed the sketchbook renders callout numbers in **two** weights. Only the
  outlined margin half ships; the filled `.pin` that pins a number onto the artwork has a
  style and no emitter, and `render_note` carried an `if False` branch where the second
  state would have gone. The claim is corrected and the gap is named — found by pointing
  `self-assess` at the plugin, which is the first time anything has
- two more CSS classes styled by nothing: `.mark-mode` in the sketchbook template (the
  chart primitive emits no such class) and `.pill` in the provenance viewer

### Added
- `scripts/vocabulary.py` — the vocabulary compiler, with `--audit` and a 35-check
  selftest. Parsed at runtime rather than compiled to a committed JSON, so there is no
  second copy to drift; per-file term counts are asserted against figures counted by hand,
  because a parser extracting zero terms makes every rule downstream pass vacuously
- `references/vocabulary/README.md` — the canonical kind legend (authored inline in only
  one of the six files until now, and checked for drift against it) and the **grade
  ceilings**, bound to terms in writing and checked against the Decoding-notes bullets
  they quote. Deriving that binding by matching prose against 223 names would produce a
  confidently wrong ceiling, which is the unsound move invariant I8 already rejects
- thirteen validator rules: `V-VOCAB-{MISSING,UNKNOWN,KIND-MISMATCH,NOT-A-TOKEN,
  RULE-NO-ANTIRULE,GRADE-CEILING,COLLISION,CONFUSED-PAIR,REGISTRY}`,
  `V-ASSET-{UNKNOWN,ORIGIN-OVERREACH}`, `V-COVERAGE-MANDATORY` and `V-CONTRAST-NO-MODE`,
  each with a planted defect and a negative control. `V-VOCAB-REGISTRY` fails **closed**:
  a registry that cannot be built would otherwise make the other twelve rules vanish silently, and
  "no findings" and "no checks" look identical from the outside
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
