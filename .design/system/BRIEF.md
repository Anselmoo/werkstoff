# BRIEF — werkstoff corporate design, retrofit pass

Built 2026-09-12 against `9077ce3`, from these inputs (mtime):

| Input | Modified |
|---|---|
| `.design/PREFLIGHT.md` | 2026-09-12T22:02 |
| `.design/system/tokens.json` | 2026-09-12T22:02 |
| `tools/design-tokens/tokens.css` | 2026-09-08T19:06 |
| `docs/.vitepress/theme/werkstoff.css` | 2026-09-08T19:06 |

**Input gate, stated rather than skipped.** `matrize-brief` stops when `system/DECODE.md` or
`system/LEXIKON.md` is missing. Both are missing. This brief is written anyway, for one
reason the approver has to accept or reject: it is a **retrofit** of the user's own grade-A,
R1 token file. PREFLIGHT marks `decode` "Not applicable" (nothing external to measure), and
the target taxonomy below is read from `tools/design-tokens/tokens.css` itself. A LEXIKON
does not exist, which is why `validate_tokens.py` reports 50× `V-VOCAB-MISSING` (see Open
questions). If that is not acceptable, the correct move is to run `matrize-name` first and
regenerate this file.

This brief is a hypothesis. The first real emit is expected to revise it.

## Direction

werkstoff keeps the silica-aerogel identity exactly as `tools/design-tokens/tokens.css`
declares it: carbon-aerogel surfaces, one aerogel chemistry per categorical slot, blue seen
against dark and amber seen through toward light. Nothing is redesigned and no existing value
moves. The pass does two things only. It **names** the handful of values the docs site and the
viewers already use but that no token holds, by appending new tokens whose values are copied
verbatim from where they are used today. Then it **stops bypasses from growing**: a CI check
flags any hard-coded colour, font family or radius in the docs theme and the viewers, and
the findings that already exist go into a baseline that may only shrink.

Target taxonomy: the 50 existing custom properties in `tokens.css` (surfaces, the five
aerogel families × three steps, `--cat-1..5`, accents, diverging pair, status scale,
typography, spacing, radii, layout, motion), plus the 7 additions settled below. Nothing else.

### Entry criteria (binding: `echo`, `spread` and `retrofit` read these)

Edit this list to steer execution. An edited criterion is honoured; a note in a chat is not.

1. `head -n 177 tools/design-tokens/tokens.css` is byte-identical to the file at `9077ce3`:
   the additions go in a **second, appended `:root { }` block**, so the 50 original
   declarations and their rationale header provably did not change.
2. `grep -cE '^\s*--[a-z0-9-]+\s*:' tools/design-tokens/tokens.css` prints `57`.
3. Every added colour token carries its measured contrast figure in its comment, copied from
   the Settled table below and reproducible with `plugins/matrize/scripts/contrast.py`.
4. `rrt artifacts --regenerate` has re-vendored every `plugins/*/assets/tokens.css` copy
   (not `--snapshot`: see CLAUDE.md, a stale lock stays green).
5. `.design/system/tokens.json` is regenerated from the new `tokens.css` by
   `retrofit_css.py`, and `emit_vitepress.py --adopt docs/.vitepress/theme/werkstoff.css
   --prefix=--wk-` then reports **0 orphans**.
6. `python3 plugins/matrize/scripts/contrast.py --selftest` exits 0 (it did at the time of writing: 9 cases, GREEN).

Invocation note: `emit_vitepress.py ... --prefix --wk-` **fails** with argparse exit 2
("expected one argument") because `--wk-` is read as an option. Write `--prefix=--wk-`.

## Settled

Every value is copied from its current use site; none is new. Contrast was computed with
`plugins/matrize/scripts/contrast.py` (WCAG 2.x) and its selftest was green in the same session.
`#f6f6f7` is VitePress's light `--vp-c-bg-soft`, taken from VitePress defaults and **not verifiable here**
(`node_modules` is absent), so the figures against it are conditional on that value.

### Additive tokens, appended to `tools/design-tokens/tokens.css`

Naming follows the file: bare dark-native role names (`--border`, `--muted`), a
`--font-*` family pair beside `--font-sans`, and a suffix only where the file has none to
express "on a light ground". `-on-light` was chosen over `-2` because `--accent-2` already
means *the second pole* (samaria), not a second shade.

| Token | Value | Copied from | Role | Contrast (measured) |
|---|---|---|---|---|
| `--accent-on-light` | `#1874c2` | `werkstoff.css:165` `--vp-c-brand-1` (light) | silica darkened for link text and the h2 origin tick on a white ground; `#348ad9` is 3.63:1 there and fails AA | 4.87:1 on `#ffffff` (AA body); 4.51:1 on `#f6f6f7` (AA body, 0.01 headroom); `#ffffff` label on it 4.87:1 |
| `--accent-on-light-strong` | `#0f66ae` | `werkstoff.css:166` `--vp-c-brand-2` (light) | a copied framework default: fills VitePress's `--vp-c-brand-2` slot (light mode) because that slot already held this value, not because a specific consumer was traced. What actually reads `--vp-c-brand-2` in the VitePress default theme — hover state is the usual reading, but this was not confirmed — is unverified (Q5); the contrast figures hold for text and a white label regardless of which UI state ends up using it | 5.95:1 on `#ffffff`; 5.50:1 on `#f6f6f7`; `#ffffff` label on it 5.95:1 |
| `--rule` | `#55616a` | `werkstoff.css` `.dark` `--wk-rule` | load-bearing section break on the dark ground: sole carrier, so WCAG 1.4.11 applies | 3.07:1 on `--bg #0a0d10` (clears 3:1 non-text) |
| `--rule-soft` | `#46515a` | `werkstoff.css` `.dark` `--wk-rule-soft` | **opinionated default**: rule used **only** where space also carries the break | 2.40:1 on `--bg` — a measurement, not a justification; see note below |
| `--rule-on-light` | `#8e8e95` | `werkstoff.css:161` `--wk-rule` (light) | load-bearing section break on white | 3.25:1 on `#ffffff`; 3.01:1 on `#f6f6f7` (clears 3:1 by 0.01) |
| `--rule-soft-on-light` | `#a7a7ac` | `werkstoff.css:162` `--wk-rule-soft` (light) | **opinionated default**: rule used only where space also carries the break | 2.40:1 on `#ffffff` — a measurement, not a justification; see note below |
| `--font-mono` | `ui-monospace, SFMono-Regular, Menlo, monospace` | 9 literal repeats in 6 viewers: arbeitsplan `run-viewer.html:35,47`; passung `matrix-viewer.html:195`; confab `burndown-viewer.html:119`; lehre `doctrine-viewer.html:93`; nacharbeit `review-viewer.html:35,47`; takt `beatgraph-viewer.html:38,52` | monospace family for data cells, code and maths in viewers | not a colour |

`--rule` and `--rule-soft` are two stops on a ramp the palette already owns. `werkstoff.css`
records them as `--border #28323a → --muted #8b9aa4` interpolated at t = 0.45 and t = 0.30.
The light pair sits on VitePress's own divider → text-3 neutral ramp. The names match
`--wk-rule`/`--wk-rule-soft` minus the prefix, so `emit_vitepress.py --prefix=--wk-` can map them by value.

**`--rule-soft`/`--rule-soft-on-light` are opinionated defaults, not derived values.** `t =
0.45` for `--rule` and `t = 0.30` for `--rule-soft` are stops this pass chose because
`werkstoff.css` already used them — no principle in this file predicts 0.30 over, say, 0.25
or 0.35; the value was copied from use, not derived from a rule. `2.40:1` is what that stop
measures against `--bg`/`#ffffff`, not a justification for choosing it — it clears nothing on
its own (it's below the 3:1 non-text floor by design) and only holds up because
`--rule-soft`'s one consumer never relies on it alone. That consumer is `.wk-breather`
(`docs/.vitepress/theme/werkstoff.css`), which its own comment describes as built so that
"deleting every one of them loses nothing" — it is aria-hidden, carries no information the
surrounding space doesn't already carry, and its own header instructs "if a reader test ever
shows space alone suffices, delete this rule and the composable that inserts it." If
`.wk-breather` goes, `--rule-soft` (and its light counterpart) would need an unused-token
check to notice they'd become dead weight — nothing here provides that check today.

PREFLIGHT counted "12 literal repeats" of the monospace stack. A grep for `monospace` over
`plugins/*/assets/*-viewer.html` and `docs/.vitepress/theme` finds **9**. The docs theme
itself already uses `var(--vp-font-family-mono)`. The 9 is the figure used here; the 12
was not reproduced.

### Every literal `emit_vitepress.py` left, and every one it did not look at

`emit_vitepress.py --tokens .design/system/tokens.json --adopt docs/.vitepress/theme/werkstoff.css --prefix=--wk-`
(exit 0): **26 literals became references, 0 ambiguous, 2 orphans.** It evaluates `--wk-*`
declarations in the first `:root` only, so the rest of the file's literals are settled here too.

| Literal | Where | Decision | Why |
|---|---|---|---|
| orphan `--wk-rule: #8e8e95` | `:root` | **becomes token** `--rule-on-light` | load-bearing, measured, used; an unnamed value nothing can check |
| orphan `--wk-rule-soft: #a7a7ac` | `:root` | **becomes token** `--rule-soft-on-light` | same |
| `--wk-rule: #55616a` | `.dark` | **becomes token** `--rule` | not seen by emit (`.dark` block); same argument |
| `--wk-rule-soft: #46515a` | `.dark` | **becomes token** `--rule-soft` | same |
| `--vp-c-brand-1: #1874c2` | `:root` | **becomes token** `--accent-on-light` | the one deliberate light-mode departure; its reason is recorded in `werkstoff.css`'s header and now gets a name |
| `--vp-c-brand-2: #0f66ae` | `:root` | **becomes token** `--accent-on-light-strong` | same family, same reason |
| `--vp-c-brand-3: #348ad9` | `:root` | **maps to existing** `var(--silica)` | identical value |
| `--vp-button-brand-text: #ffffff` | `:root` | **named baseline exception** | white is not a member of the aerogel palette, and inventing `--white` would add a token with no brand meaning. VitePress may already define a white token (`--vp-c-white`); that could not be confirmed with `node_modules` absent (Open questions) |
| the 26 mapped `--wk-*` hex mirrors | `:root` | **map to existing** (`--wk-bg: var(--bg)` … `--wk-status-unknown: var(--status-unknown)`) | emit's proposed mapping, value-identical |
| `rgba(52,138,217,a)` ×11 | theme css + `PairingCards.vue` | **maps to existing** `--silica` via `color-mix` | `#348ad9` = 52,138,217 |
| `rgba(207,182,86,a)` ×5 | hero gradient, `RecipeBeats.vue`, `PairingCards.vue` | **maps** `--samaria-light` | `#cfb656` |
| `rgba(8,147,92,a)` ×4 | recipe cards, pairing cards | **maps** `--chromia` | `#08935c` |
| `rgba(171,143,0,a)` ×4 | same | **maps** `--samaria` | `#ab8f00` |
| `rgba(171,109,198,a)` ×4 | same | **maps** `--neodymia` | `#ab6dc6` |
| `rgba(189,81,55,a)` ×2 | recipe cards | **maps** `--ferria` | `#bd5137` |
| `rgba(76,141,90,.12)`, `rgba(181,139,58,.12)`, `rgba(176,80,63,.12)`, `rgba(74,113,156,.12)` | `.dark` custom blocks | **map** `--status-good`, `--status-warn`, `--status-bad`, `--status-unknown` | value-identical |
| `rgba(255,255,255,.85)` | `passung/assets/matrix-viewer.html:159` | **named baseline exception** | neutral overlay, not a brand colour |
| `rgba(0,0,0,.5)` | `lehre/assets/doctrine-viewer.html:111` (box-shadow) | **named baseline exception** | shadow, not a brand colour |
| off-token hex in viewers: `stage-map-viewer.html` (4), `derivation-viewer.html` (9), `architecture-tree-viewer.html` (1), incl. `#111`/`#fff`/`#ccc` | viewers | **named baseline exceptions, carried unsettled** | PREFLIGHT lists them as findings for `matrize-retrofit`; deciding each needs the viewer's data shape, which this brief does not have |

Every `rgba()` triple in the docs theme is a token colour, and the check confirms it.
No new alpha tokens are needed: each becomes `color-mix(in srgb, var(--token) N%, transparent)`,
e.g. `rgba(52, 138, 217, 0.14)` → `color-mix(in srgb, var(--silica) 14%, transparent)`.

## Not adopted

- **No change to any existing value.** Includes `--accent: var(--silica)` staying `#348ad9`
  even though it fails AA on white. Light mode gets its own named token instead.
- **No docs spacing scale in `tokens.css`.** `--wk-space-1..24` (4–96px, √2 ladder) stays a
  docs-local scale this pass (see Unnamed).
- **No `--white` / `--black` tokens.** They carry no aerogel meaning; the three neutral
  literals above are named exceptions instead.
- **No alpha-variant tokens** (`--silica-14` etc.). `color-mix` over the existing token
  expresses all 34 theme `rgba()` uses (22 in `werkstoff.css`, 12 in `components/*.vue`)
  without multiplying the token count.
- **No `--cat-6`, no token for the 8-hue ramp PREFLIGHT lists under "matrix".** The brand rule
  caps the categorical palette at five. A sixth series folds into "Other" or facets.
- **No light-mode status or categorical tokens.** VitePress's own light neutrals stay, as
  `werkstoff.css` already argues ("forcing a dark-native palette into light mode buys nothing").
- **No raising of `--vp-c-divider`.** Only load-bearing uses are repointed, as today.

## Unnamed

Recorded, and **deliberately not invented in this pass**. Naming a scale from literals is a
design decision this retrofit does not have the evidence to make.

| Scale | Tokens today | Literals in use | Checked by |
|---|---|---|---|
| Radius | `--radius-sm 4px`, `--radius-control 6px`, `--radius-panel 8px` | 26 non-zero px `border-radius` literals across theme + viewers: 4px×7, 2px×6, 999px×4, 12px×2, 8px×2, 9px×2, 6px×2, 3px×1 (scratch regex; the CI script's first run is authoritative). Also `50%`, which is not a px literal | **T-RADIUS**, with its shrink-only baseline. A 4/6/8px literal may be rewritten to the existing token of the same value; 2, 3, 9, 12 and 999px stay unnamed |
| Font size | `--font-size-base 14px` only | ~14 literal sizes (PREFLIGHT's figure; not re-measured here) | **nothing.** None of the four rules inspects `font-size` |
| Spacing | `--space-1..5` = 4/8/12/16/20px | docs `--wk-space-1..24` = 4/8/12/16/24/32/48/64/96px. Steps 1–4 agree in name and value; the token scale has 20px and the docs scale does not; `--wk-space-6` (24px) has no token counterpart | **nothing.** None of the four rules inspects spacing |

The dispatch described all three scales as "covered by the shrink-only lint baseline". That
is true only for radius. Font size and spacing have **no** rule, so a new literal there is
invisible to CI. That is recorded as an open question, not papered over.

## Open questions

Follow-ups, not settled here.

1. **50× `V-VOCAB-MISSING` (blocker)** from `validate_tokens.py .design/system/tokens.json`
   (exit 1). No token carries `com.werkstoff.matrize.vocab.term`, because no `LEXIKON.md`
   exists. Run `matrize-name`. After this pass the count is expected to be 57.
2. **10× `V-TYPE-MISSING` (major)** on the `var()` alias tokens: `color.cat-1..5`,
   `color.accent`, `color.accent-2`, `color.diverging-cool/-warm/-mid`. `retrofit_css.py` emits
   aliases without `$type`. This is a matrize tooling gap and needs a matrize change, so it is out of scope for a no-bump pass.
3. **How `tokens.css` reaches the docs build.** emit's proposed layer writes `--wk-bg: var(--bg)`,
   which resolves only if `tokens.css` is loaded by VitePress. `werkstoff.css`'s header says an
   `@import` from `tools/` breaks the build. Candidate: an `.rrt.toml` `artifact_targets` copy at
   `docs/.vitepress/theme/tokens.css` (a "tokens.css copy", exempt from the lint), imported by
   `theme/index.js`. Unverified until `npm ci` makes `npm run docs:build` runnable.
4. **Does VitePress define a white token** (`--vp-c-white`) to replace `--vp-button-brand-text: #ffffff`?
   Not answerable without `node_modules`; the literal stays a baseline exception until it is.
5. **What exactly consumes `--vp-c-brand-2`** in the VitePress default theme (hover state is the
   usual reading)? A context7 lookup returned the default values but not the consumers. The
   contrast figures above hold for text and for a white label either way.
6. **Font-size and spacing have no enforcement.** Either add T-FONT-SIZE / T-SPACING rules with
   their own baselines, or accept them as unguarded. It is decided by nothing today.
7. **Colours computed in JS evade all four rules.** `plugins/befund/assets/stage-map-viewer.html:198`
   builds `rgba(${(n >> 16) & 255},…)` from integers; T-COLOR-FN only matches literal arguments.
   PREFLIGHT's "matrix (8-hue ramp)" is the same risk wherever that ramp is expressed as numbers.
8. **`#f6f6f7`** as VitePress's light `--vp-c-bg-soft` is assumed, not read from source. `--accent-on-light` on it
   is 4.51:1, **0.01 above AA**. If the real value is any darker, link text in light-mode tip
   blocks fails AA.
9. **Focus/disabled/loading/empty states have no tokens and no rules** (owner: unassigned —
   needs a `matrize-name` pass). One focus ring already exists, unnamed:
   `outline: 2px solid var(--vp-c-brand-1); outline-offset: 2px;` in both
   `docs/.vitepress/theme/components/BeatSkillRefs.vue:74-75` and
   `RecipeBeats.vue:212-213` — a real, working ring that reads a VitePress framework
   token directly rather than a werkstoff one. Working the other direction, at least three
   viewers *remove* the browser default without replacing it:
   `plugins/lehre/assets/doctrine-viewer.html:73` (`.snode:focus { outline: none; }`),
   `plugins/matrize/assets/provenance-viewer.html:54` (`.node:focus { outline: none; }`), and
   `plugins/befund/assets/stage-map-viewer.html:66` (`outline: none` on a focusable
   element). None of the four T-* rules would catch either shape — there is no
   T-FOCUS-RING and no rule that flags an `outline: none` with no visible replacement.
   Disabled, loading and empty states have neither a token nor a rule at all. Also open:
   content rules (voice/tone/microcopy for the docs and viewers), and a reduced-motion
   anti-rule for `--transition-fast`/`--transition-base` — coverage today is partial, not
   absent, which is exactly why an explicit rule is missing rather than obviously needed:
   `docs/.vitepress/theme/werkstoff.css`'s `.VPLink`/`.vp-doc a` rule and
   `components/PluginGrid.vue`'s `.plugin-card` both carry a
   `@media (prefers-reduced-motion: reduce)` carve-out for their `var(--wk-transition-fast)`
   use, but every `var(--transition-fast)` use in the three viewers that reference it directly
   — `plugins/andon/assets/board-viewer.html:102`, `plugins/confab/assets/burndown-viewer.html:26`,
   and the three uses in `plugins/lehre/assets/doctrine-viewer.html:75,102,112` — has no
   `prefers-reduced-motion` guard at all, so those transitions fire unconditionally for a
   viewer who has asked the OS to suppress motion. No rule here would catch either the
   presence or the absence of that guard.

### Coverage (matrize-brief's six areas and three mandatory asset classes)

| Area | Covered? |
|---|---|
| States (hover/focus/disabled) | **No.** Only `--accent-on-light-strong` touches a state, and its consumer is unverified (Q5) |
| Contrast | **Yes** for every added colour token (table above) and for the 50 originals (`tokens.css` header) |
| Motion | Partly: `--transition-fast/-base` exist; no reduced-motion rule |
| Inverse mode | **Yes** for rules and accent (light/dark pairs); viewers are dark-only by PREFLIGHT |
| Content rules | **No** |
| Provenance | **Yes**: every added value names its source line |
| Empty state / error state / Open Graph image | **Not covered** by this pass |

## What would disprove this

Each of these is observable. If any is seen, the direction does not hold.

- `head -n 177 tools/design-tokens/tokens.css` differs from `9077ce3`. Then the pass changed an existing
  value, and it was not a retrofit.
- After the additions and `retrofit_css.py`, `emit_vitepress.py --prefix=--wk-` still reports an
  orphan, or reports an **ambiguous** literal. Then two tokens share a value that means two things,
  and the naming above is wrong.
- A theme `rgba()` rewritten to `color-mix(in srgb, var(--token) N%, transparent)` renders a
  different pixel colour than before. Then the "maps to existing" decisions are wrong.

  **Observed, and scoped (2026-09-12, after this brief).** The pixel proof
  (HEAD content + retrofitted theme vs HEAD, 7 pages × light/dark, harness calibrated
  identical-on-identical and red on a planted accent change) found exactly one case: the two
  hero-image gradient stops. 84 327 light / 83 933 dark pixels moved inside the blurred
  backdrop, max channel delta 4/255. Cause, from a computed-style diff: `color-mix()` computes
  to a non-legacy `color(srgb …)` value, and a gradient holding one interpolates in OKLab rather
  than sRGB. `linear-gradient(120deg in srgb, …)` reduced it to ~10k pixels, not zero. The
  colour mapping is right; the *interpolation space* is not preserved inside gradients. Those two
  stops stay `rgba()` literals, commented in `werkstoff.css` and carried in the baseline
  (T-COLOR-FN 2). Every other `color-mix()` rewrite renders pixel-identical, so the bullet is
  refuted for gradients only.
- A view needs a sixth categorical hue and neither "Other" nor faceting can serve it. Then the
  five-chemistry cap does not hold for this repo.
- The docs spacing scale cannot be expressed without 20px, or a viewer table cannot be expressed
  in 4–96px. Then the two scales are one scale and "Unnamed" was the wrong call.
- The CI check's first run over the unchanged tree reports a finding the baseline does not
  carry. Then the instrument is miscalibrated. Fix the check, not the baseline.
- A planted `#ff0000`, `rgb(1,2,3)`, `font-family: Arial` or `border-radius: 5px` in a viewer is
  **not** flagged. Then the check cannot fail, and every green run afterwards means nothing.
- `--accent-on-light` measures below 4.5:1 on the real light `--vp-c-bg-soft` (Q8).

## Corporate design usage rules

The token source is `tools/design-tokens/tokens.css`. A colour, font family or radius used in the docs
theme or a report viewer is a **reference** to it (`var(--token)`), never a restatement. The
check is `scripts/ci/check_design_tokens.py`, over:

- `docs/.vitepress/theme/**` (`.css`, `.vue`, `.js`)
- `docs/.vitepress/config.mjs`
- `plugins/*/assets/*-viewer.html`
- `plugins/matrize/assets/*template*.html`

It enforces four rules, each matching a specific property-usage shape rather than any mention
of a colour/font/radius value — a `--wk-*` custom-property *declaration* holding a literal
(e.g. `--wk-radius-sm: 4px;`) is not itself a finding under any rule; only *using* it with a
literal is. Each finding names rule, file and line.

| Rule | Flags | Not a finding |
|---|---|---|
| **T-HEX** | a literal hex colour (`#rgb`, `#rgba`, `#rrggbb`, `#rrggbbaa`) in a declaration **value**, including inside a `var()` fallback | an id selector; a URL fragment |
| **T-COLOR-FN** | `rgb()`, `rgba()`, `hsl()`, `hsla()`, `hwb()` or `oklch()` with a **literal main channel** (R/G/B or H/S/L) | `color-mix(in srgb, var(--token) N%, transparent)`; a colour function whose main channels are all `var()`, even when alpha is a literal (`rgba(var(--r), var(--g), var(--b), 0.5)`) |
| **T-FONT-FAMILY** | `font-family:`/`font:` naming a family literally; also a JS `.font = "..."` canvas assignment or a `fontFamily: "..."` object property | `var(--font-sans)`, `var(--font-mono)`, `var(--vp-font-family-*)`; a CSS-wide keyword alone (`inherit`, `initial`, `unset`); a template literal whose family part is entirely `${...}` |
| **T-RADIUS** | `border-radius` or a `border-(top\|bottom)-(left\|right)-radius` longhand with a **non-zero px literal**, including a `var(--radius-sm, 4px)` fallback | `0`, `var()` with no literal fallback, a percentage (`50%`); a `--wk-radius-*` custom-property declaration itself (no rule matches that syntax) |

A literal inside a `var()` fallback counts. A fallback is a second source of the value, and it
silently wins whenever the token fails to load. That is the "looks correct and silently does
nothing" shape this repo catalogues.

**Exempt:**

- CSS comments `/* … */` and HTML comments `<!-- … -->`. Contrast figures in prose are documentation, not values.
- A `tokens.css` file that is **byte-for-byte identical** to `tools/design-tokens/tokens.css` —
  checked by content, not filename. `plugins/*/assets/tokens.css` (the 12 vendored copies)
  isn't in the scanned surfaces at all, so it's moot there; the one place this exemption can
  actually apply is `docs/.vitepress/theme/tokens.css`. A `tokens.css` that has diverged from
  the source (hand-written, stale, or otherwise different) is scanned like any other file —
  the exemption is for being the source, not for the filename.

**Baseline.** Findings that exist when the check lands go in
`scripts/ci/design-tokens-baseline.txt`, one `<path>\t<rule>\t<count>` per line (tab-separated). It **may only shrink**:

- a path not in the baseline with any finding fails;
- a count above its baseline fails;
- a count **below** its baseline also fails, with "lower the baseline to N". The floor ratchets,
  so a fixed finding cannot silently come back.

Counts are per file and per rule, not per line, so an unrelated edit does not churn the file. At
the time of writing, a scratch regex put the tree at roughly T-HEX 48, T-COLOR-FN 36 (34 theme + 2 viewer; `grep -oE 'rgba?\('` exact),
T-FONT-FAMILY 9, T-RADIUS 26. The script's own run is the authoritative figure. After the
retrofit, the hardened rules and all three viewer migrations (cli-scaffold first; stage-map and
matrix on a third attempt, see `retrofit-report.md`), it records T-HEX 27, T-COLOR-FN 8,
T-FONT-FAMILY 3, T-RADIUS 33 (71 findings, 24 entries), after five viewers adopted `--font-mono`.

**Writing new code:**

- Need a colour that is not a token? Add it to `tokens.css` first, value copied from its source
  and contrast measured with `plugins/matrize/scripts/contrast.py` in its comment. Then
  `rrt artifacts --regenerate`, then reference it.
- Need a translucent token colour? Use `color-mix(in srgb, var(--token) N%, transparent)`.
  Never `rgba()` of the token's channels.
- In the docs theme, declare a `--wk-*` name as `var(--token)`; VitePress `--vp-*` framework
  tokens are acceptable `var()` targets.
- Never add a path to the baseline or raise a number in it. Fix the code instead.
- The check's self-test plants one finding per rule and one per exemption, and must go red on each rule and stay green on each exemption. Run it before trusting a green run.

---

```
This is a discussion basis, not a finished rulebook.

Decision-maker: ______________________
Gate criteria:  feedback on the 7 token names and values, the "Not adopted" list, and the
                four T-* rules with their var()-fallback decision, before production
Approved by: ________________  Date: __________
Approval covers: <direction only> | <direction and taxonomy> | <the whole system>
```

Nothing further is written from this brief until that block is signed. No objection is not approval.
