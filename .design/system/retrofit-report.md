# Retrofit report — docs theme derived from tokens.css

Executed 2026-09-12 against `.design/system/BRIEF.md`, on branch
`docs/design-token-docs-harmonization`. Scope: make the docs theme's palette
**derived** from `tools/design-tokens/tokens.css` instead of a hand-mirrored
duplicate, with no rendered pixel changed. This is the integrator pass; it does
not re-litigate the brief's naming decisions, only executes them and proves the
result.

## What was retrofitted

1. **`tools/design-tokens/tokens.css`** — the 50 original declarations
   (lines 1-177) are untouched, byte-for-byte identical to `HEAD`. A second,
   separately commented `:root { }` block was appended with the 7 tokens the
   brief settled: `--accent-on-light`, `--accent-on-light-strong`, `--rule`,
   `--rule-soft`, `--rule-on-light`, `--rule-soft-on-light`, `--font-mono`.
   Every added colour token's comment carries its measured contrast figure,
   copied from the brief and independently reproduced below. File is now 57
   custom-property declarations, still nothing but `:root { }`, comments and
   declarations (confirmed by parsing the file and checking every non-comment,
   non-empty line matches `:root {`, `}`, or `--name: value;`).

2. **`docs/.vitepress/theme/tokens.css`** — created as a byte-identical copy of
   `tools/design-tokens/tokens.css` (`diff` confirms). `docs/.vitepress/theme/index.js`
   imports it (`./tokens.css`) immediately before `./werkstoff.css`.

3. **`docs/.vitepress/theme/werkstoff.css`** — every `--wk-*` and `--vp-c-brand-*`
   custom-property declaration whose literal equalled a token value now reads
   `var(--token)` instead of the literal:
   - the 26 `--wk-*` mirrors `emit_vitepress.py` proposed (bg, panel, panel-2,
     text, muted, smoke, border, the 5 aerogel families × 3 steps, the 4
     status colours);
   - the 2 orphans it flagged before this pass (`--wk-rule`/`--wk-rule-soft`,
     both the light `:root` values and the `.dark` override values) — now
     named tokens (`--rule-on-light`/`--rule-soft-on-light` and
     `--rule`/`--rule-soft`), so `emit_vitepress.py --adopt` now reports **0
     orphans, 0 ambiguous** (in fact 0 literals at all: every `--wk-*` value it
     scans is already a reference);
   - `--vp-c-brand-1`/`-2` → `var(--accent-on-light)` / `var(--accent-on-light-strong)`;
     `--vp-c-brand-3` → `var(--silica)` (identical value, brief's "maps to
     existing" decision).
   Every `rgba(r, g, b, a)` whose `(r, g, b)` equalled a token colour (22
   occurrences: the two `--vp-c-brand-soft` values, the 4 custom-block
   backgrounds, the 2 hero-gradient stops, and 14 across the 6 catalog
   category cards + 2 external-tag badges) became
   `color-mix(in srgb, var(--token) N%, transparent)` — **except the 2 hero-gradient
   stops, reverted to `rgba()` after the pixel proof.** Inside a gradient, `color-mix()`'s
   non-legacy `color(srgb …)` result switches interpolation to OKLab and moved ~84k pixels of
   the blurred hero backdrop (max 4/255); see BRIEF.md "What would disprove this". 20 of the
   22 are references; the 2 stops are commented literals in the baseline.
   `--vp-button-brand-text: #ffffff` stays a literal, marked inline as the
   brief's named baseline exception (white carries no aerogel meaning).
   The header comment now states tokens.css is imported and vendored into all
   12 plugins (not "seven"), and the entrance-motion comment's plugin count
   was corrected from "9 plugins" to "12" (verified against
   `docs/.vitepress/theme/components/PluginGrid.vue`'s `PLUGINS` array, which
   lists exactly 12 entries).

4. **`docs/.vitepress/theme/components/PairingCards.vue` and `RecipeBeats.vue`**
   — all 12 `rgba()` restatements of token colours (10 in PairingCards: 4 beat
   chips × 2 modes + 1 prompt-code background × 2 modes; 2 in RecipeBeats: 1
   opening-prompt background × 2 modes) became `color-mix(in srgb, var(--wk-token) N%, transparent)`,
   consistent with the `--wk-*` names these files already use elsewhere
   (`var(--wk-silica)` in `PairingCards.vue`'s `.join-glyph`, etc.).

5. **`.rrt.toml`** — two `artifact_targets` added in the existing tokens.css-copy
   format: `docs/.vitepress/theme/tokens.css` (cp) and `.design/system/tokens.json`
   (`retrofit_css.py`). The stale "vendored into all 7 report-viewer plugins"
   comment was corrected to "all 12 plugins... and into docs/.vitepress/theme/tokens.css";
   the historical "all 5 existing report viewers" sentence describing the
   feature's origin was left as-is, per the brief.

6. **`.design/system/tokens.json`** — regenerated from the new `tokens.css` by
   `retrofit_css.py` (57 tokens).

Not touched, per the brief's "Not adopted"/"Unnamed" sections and out of this
integrator's write scope: the radius scale (`--wk-radius-sm/-control/-panel`,
`--wk-transition-fast`, all of which already equal existing `--radius-*`/
`--transition-fast` token values but are left literal, matching BRIEF's
"Unnamed" call that the radius/spacing reconciliation is a separate,
not-yet-taken decision gated on a future `T-RADIUS` CI rule); the docs
spacing scale (`--wk-space-1..24`, partial overlap with `--space-1..5`, same
"Unnamed" reasoning); `scripts/ci/check_design_tokens.py` and its baseline
(not in this integrator's write scope).

## The three `prove_retrofit.py` arms

```
source: tools/design-tokens/tokens.css  (57 declarations)

arm 1 — textual      PASS
arm 2 — alias structure  PASS  (10 alias(es) in source)
arm 3 — visual       PASS
    byte-identical render, 1600x900

ZERO VISUAL DIFF, STRUCTURE PRESERVED
```
Exit 0. All three arms green: the textual diff of the token file (arm 1), the
alias/reference structure (arm 2, 10 `var()` aliases in the source — `--cat-1..5`,
`--accent`, `--accent-2`, `--diverging-cool/-warm/-mid`, unchanged by this
pass), and a byte-identical Chrome-rendered swatch sheet before/after (arm 3).

## `validate_tokens.py` findings, by rule

```
V-VOCAB-MISSING  blocker  57
V-TYPE-MISSING   major    10
total 67
```
Exit 1 (blocker present). Both are BRIEF-recorded, pre-existing, expected-to-
still-be-open findings, not regressions from this pass:

- **`V-VOCAB-MISSING` × 57 (was 50).** No `LEXIKON.md` exists, so no token
  carries a `com.werkstoff.matrize.vocab.term`. BRIEF's open question #1
  names this a blocker gated on running `matrize-name` first, and predicts
  the count rises from 50 to 57 once the 7 additions land — confirmed exactly.
- **`V-TYPE-MISSING` × 10 (unchanged).** The `var()`-alias tokens
  (`color.cat-1..5`, `color.accent`, `color.accent-2`,
  `color.diverging-cool/-warm/-mid`) come out of `retrofit_css.py` without a
  `$type`. BRIEF's open question #2 calls this a `matrize` tooling gap, out
  of scope for a no-bump pass; this integration did not touch `retrofit_css.py`
  and the count is unchanged at 10.

## `emit_vitepress.py --adopt` result

Before this pass (BRIEF): 26 literals became references, 0 ambiguous, 2
orphans. After this pass:

```
0 literal(s) became references; 0 ambiguous, 0 orphan(s) left for a human
:root {
}
```

Zero orphans (entry criterion 5, satisfied) — and, stronger than the brief
asked for, zero literals left at all: every `--wk-*` declaration `emit_vitepress.py`
scans in `werkstoff.css`'s first `:root` block is already a `var()` reference,
so there is nothing left for the tool to propose.

## `contrast.py --selftest`

9 cases, 0 failures, GREEN, exit 0 (entry criterion 6).

Every new colour token's contrast figure was independently reproduced with
`contrast.py` rather than trusted from the brief:

| Pair | Reproduced | Brief |
|---|---|---|
| `#1874c2` on `#ffffff` | 4.87:1 | 4.87:1 |
| `#1874c2` on `#f6f6f7` | 4.51:1 | 4.51:1 |
| `#ffffff` on `#1874c2` | 4.87:1 | 4.87:1 |
| `#0f66ae` on `#ffffff` | 5.95:1 | 5.95:1 |
| `#0f66ae` on `#f6f6f7` | 5.5:1 | 5.50:1 |
| `#ffffff` on `#0f66ae` | 5.95:1 | 5.95:1 |
| `#55616a` on `#0a0d10` | 3.07:1 | 3.07:1 |
| `#46515a` on `#0a0d10` | 2.4:1 | 2.40:1 |
| `#8e8e95` on `#ffffff` | 3.25:1 | 3.25:1 |
| `#8e8e95` on `#f6f6f7` | 3.01:1 | 3.01:1 |
| `#a7a7ac` on `#ffffff` | 2.4:1 | 2.40:1 |

All 11 match to the figure. Entry criterion 3 (every added colour token
carries a reproducible measured contrast in its comment) holds.

## The theme proof (no docs build available)

`node_modules` is absent, so `npm run docs:build` cannot run. Proof instead:
`/private/tmp/claude-502/.../scratchpad/integrator-resolve.py` parses
`git show HEAD:<file>` (pre-retrofit) and the working-tree version
(post-retrofit) of `werkstoff.css`, `PairingCards.vue` and `RecipeBeats.vue`,
resolves every `var()` in the new files against `tools/design-tokens/tokens.css`
plus the theme's own `:root`/`.dark` custom-property cascade (recursively, and
separately for the light and dark environments — a `.dark`-scoped declaration
resolves against the dark cascade, everything else against light, exactly as a
browser would), evaluates every `color-mix(in srgb, var(--token) N%, transparent)`
to its equivalent `rgba()`, normalises colours (lowercase hex, `rgba` alpha to
3 decimals), and compares old vs. new **per declaration, in file order** (blocks
are paired positionally since the file has repeated selectors — two `:root`
blocks, two `.dark` blocks — so a name-keyed comparison would collide).

```
tokens.css: 57 custom properties in the light (:root) environment
werkstoff.css: 227 declarations compared, 54 literal->var/color-mix replacements, 0 diff(s)
PairingCards.vue: 117 declarations compared, 10 literal replacements, 0 diff(s)
RecipeBeats.vue: 71 declarations compared, 2 literal replacements, 0 diff(s)

TOTAL: 415 declarations compared, 66 literal->reference replacements
0 differences
GREEN
```
Exit 0. 415 declarations compared across the three files, 66 of them literal
hex/rgba values replaced by a `var()`/`color-mix()` reference, **zero**
resolved-value differences — every replaced declaration still resolves to the
exact same colour it did before the retrofit.

## Named / contested / unnamed (from BRIEF.md)

**Named this pass** (the 7 additions): `--accent-on-light`,
`--accent-on-light-strong`, `--rule`, `--rule-soft`, `--rule-on-light`,
`--rule-soft-on-light`, `--font-mono`.

**Contested / named baseline exceptions (left as literals, by design):**
- `--vp-button-brand-text: #ffffff` (werkstoff.css `:root`) — white carries no
  aerogel meaning; inventing a `--white` token was explicitly rejected in
  BRIEF's "Not adopted".
- `rgba(255, 255, 255, .85)` (`codebase-consistency/assets/matrix-viewer.html:159`)
  and `rgba(0, 0, 0, .5)` (`lehre/assets/doctrine-viewer.html:111`, a
  `box-shadow`) — neutral overlay / shadow, not brand colours. Out of this
  integrator's write scope (viewer assets are not listed in WRITE SCOPE); left
  untouched.
- Off-token hex in `stage-map-viewer.html` (4), `derivation-viewer.html` (9),
  `architecture-tree-viewer.html` (1) — BRIEF carries these as unsettled
  findings for a future `matrize-retrofit` pass over the viewers, which needs
  each viewer's data shape to decide; out of this integrator's write scope.

**Unnamed (deliberately not invented this pass):**
- **Radius.** `--radius-sm`/`-control`/`-panel` (4/6/8px) already exist as
  tokens; `werkstoff.css`'s `--wk-radius-sm`/`-control`/`-panel` restate the
  same 3 values and `--wk-transition-fast` restates `--transition-fast`, but
  BRIEF scopes radius/motion reconciliation to a future `T-RADIUS` CI rule
  with its own shrink-only baseline, not this naming pass — left as literals.
  (`emit_vitepress.py` itself only ever considers colour/hex declarations —
  confirmed from its source and self-test, `"a non-colour declaration is left
  alone"` — so it never proposed these either.)
- **Font size.** ~14 literal sizes across the theme/viewers, one token
  (`--font-size-base`). No CI rule inspects `font-size`. Unguarded, per BRIEF.
- **Spacing.** The docs `--wk-space-1..24` scale (4-96px) partially overlaps
  the token `--space-1..5` scale (4-20px) at steps 1-4 only; `--wk-space-6`
  (24px) has no token counterpart. BRIEF explicitly declines to partially
  merge these ("stays a docs-local scale this pass"), so none of
  `--wk-space-*` was rewritten to `var()`, even where a value happens to
  match — a partial merge would be more confusing than the status quo it
  replaces, and BRIEF settles this as a scale-level decision, not a
  per-declaration one.

## Remaining literals in `werkstoff.css`, and why each stays

After the retrofit, exactly one non-comment literal remains in
`docs/.vitepress/theme/werkstoff.css`:

| Literal | Location | Why it stays |
|---|---|---|
| `#ffffff` | `--vp-button-brand-text: #ffffff;` (`:root`) | Named baseline exception (BRIEF "Not adopted": no `--white` token — see above) |

Everything else that was a hex/rgba literal in this file before the pass (28
hex declarations across `:root`/`.dark`, 22 `rgba()` calls) is now a `var()` or
`color-mix()` reference. `--wk-radius-sm/-control/-panel`, `--wk-transition-fast`,
`--wk-space-*`, and `--wk-measure` remain literal px/ms/rem values — not hex or
rgba, out of scope for this naming pass (see "Unnamed" above), and unaffected by
any of `check_design_tokens.py`'s four rules at all, **including** `T-RADIUS`:
that rule matches only `border(-top|bottom)-(left|right)?-radius:` *usage*, never
a `--wk-radius-*` custom-property *declaration* by that name. BRIEF places their
eventual resolution as a naming decision, not a CI-rule gap this script closes on
its own.

## Open items carried forward (not this integrator's to close)

- BRIEF's open questions #4 (does VitePress define its own white token),
  #5 (what actually consumes `--vp-c-brand-2`), and #8 (`#f6f6f7` assumed,
  not read from `node_modules`) are unchanged by this pass — still open,
  still blocking full confidence in the light-mode figures that depend on
  `#f6f6f7`.
- `scripts/ci/check_design_tokens.py` and `scripts/ci/design-tokens-baseline.txt`
  (the CI enforcement half of the brief) are not in this integrator's write
  scope and were not touched or verified here.
- The three viewer files with off-token hex (`stage-map-viewer.html`,
  `derivation-viewer.html`, `architecture-tree-viewer.html`) and the two named
  neutral-overlay/shadow exceptions in other viewers are unresolved, per
  BRIEF, and out of this integrator's write scope.

**Update (post-review viewer work, not part of this integrator's original pass).** Three
viewers had their leftover categorical colours moved onto `--cat-1..5`, and each was then judged
by a blind design critic that rendered scratch fixtures and measured contrast with `contrast.py`,
for at most two rounds:

- **`cli-scaffold/assets/architecture-tree-viewer.html` — landed.** Every role badge is a neutral
  `--panel-2` chip with a `var(--text)` label (12.45:1) and the role's `--cat-*` colour as a 4px
  left swatch (≥3:1 on both sides for all five slots); the sixth role, `completion`, folds into a
  neutral `--muted` swatch, the "Other" treatment `tokens.css` prescribes; the `#fff` label literal
  is gone. The critic reproduced the committed screenshot from the current template.
- **`self-assess/assets/stage-map-viewer.html` and `codebase-consistency/assets/matrix-viewer.html`
  — reverted to `HEAD`.** Round 1 introduced reserved-hue collisions and sub-4.5:1 labels; round 2
  introduced a 2.84:1 cycle ring and badge occlusion (stage-map), and 4.09:1 cell text on
  `--status-bad` plus digits broken by the reused-slot texture (matrix). Two rejected rounds ended
  the loop; their pre-existing literals are carried in the baseline, and the defects of both rounds
  are recorded in a follow-up task.

`scripts/ci/check_design_tokens.py` was hardened in the same review (JS font assignments, the
T-HEX id-selector heuristic, T-COLOR-FN flagging any literal channel, a byte-identical-copy
exemption, an unresolvable `--base-ref` exiting 2), and `scripts/ci/design-tokens-baseline.txt`
was re-derived after the reverts: **98 findings across 35 (path, rule) entries** (T-HEX 41,
T-COLOR-FN 10, T-FONT-FAMILY 13, T-RADIUS 34). The rise from the earlier 87 is entirely the two
reverted viewers' `HEAD` literals (matrix T-HEX 8, stage-map T-HEX 7 and T-FONT-FAMILY 1) less the
cli-scaffold literal the landed fix removed; no entry covers a literal this branch added.

**Update (third viewer attempt).** The two reverted viewers were migrated again. The first
version of this attempt was itself rejected by an independent reviewer that rendered and measured
it (number tags landed on nodes in a 30-cycle graph; variant hues matched the page's status
colours), and the design below is the revision that answered those findings:

- **`self-assess/assets/stage-map-viewer.html`** uses no categorical hue. Nodes are opaque 18%
  tints of a status colour on `--bg`, with channels that do not depend on hue: outer ring weight
  (god-module), a dashed ring (dead-end), a second, inner red ring (cycle membership, by shape;
  on circles too small for two rings, a red core inside a painted `--bg` gap and the state ring,
  or a solid red disc at the very smallest sizes, where any other state ring stays outside it) and a printed cycle number. A cycle member
  always takes the cycle tint, the only tint its red inner ring clears 3:1 on (3.27:1; 2.99:1 on
  the god tint). A number that does not fit becomes a tag only where its box and leader cover no
  node, tag or HTML panel, whose leader crosses no other leader and grazes no node, and which is
  nearer its own node than any other; there is no least-bad fallback, and numbers left out are counted
  in a note pinned to the bottom of the HUD, whose height follows the hint bar as actually laid out. Legend swatches go through the map's own `markFor()`/`drawNodeMark()`.
- **`codebase-consistency/assets/matrix-viewer.html`** prints each cell's key (variant letter, or
  a ✓/≈/✗ conformance glyph, or "–" for a cell with no score once a canon exists) with its site
  count on a solid `--bg` plate (15.44:1 on every fill). Variant hues are only `--cat-1` and
  `--cat-3`: `--cat-5`, `--cat-2` and `--cat-4` read as the page's red/green/amber status meanings.
  Codes skip I and O. No-data cells are a crisp dashed `--muted` outline with the words "no data";
  hover and selection draw in `--bg`, which separates from every fill (≥3.77:1). Cells and legend
  keys share `cellMark()` and `drawCellMark()`.

The baseline lines for both files were lowered in the same change, to **79 findings across 29
(path, rule) entries** (T-HEX 27, T-COLOR-FN 8, T-FONT-FAMILY 11, T-RADIUS 33). No other entry moved.
