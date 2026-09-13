---
title: Design tokens
---

# Corporate design usage

Read this before adding a colour, font family, or radius anywhere in
`docs/.vitepress/theme/**` or a `plugins/*/assets/*-viewer.html`. Both surfaces are graded
by `scripts/ci/check_design_tokens.py`, and both are covered by the same four rules and the
same shrink-only baseline.

## The source-of-truth chain

There is exactly one place a token value is allowed to originate:
`tools/design-tokens/tokens.css`. Everything else is a copy, a reference, or a derived
artefact — never a second original.

1. **`tools/design-tokens/tokens.css`** — the source. 57 custom properties (50 original
   plus 7 added in the retrofit pass this page documents). Coverage is uneven, not
   uniform: the aerogel families' `-light` steps, `--smoke`, `--header-h`, `--status-warn`,
   and all 7 retrofit additions each carry their own comment (a colour one states its
   measured contrast); most of the rest share one group heading above several
   declarations (`--bg`/`--panel`/`--panel-2`/`--text`/`--muted`/`--border` under
   "Surfaces", `--silica`/`--silica-deep` and the other base/deep steps under the aerogel
   family heading, `--cat-*`/`--accent*`/`--diverging-*` each under their own section
   comment) with no per-declaration note and no per-declaration contrast figure — the file's
   header block states `--text`/`--muted`/`--accent`/`--smoke` against `--bg` once, and the
   `-deep` steps' contrast as a 2.07–3.17:1 range, not one number per token. The 67-line
   rationale header at the top of the file is the brand authority
   [`report-viewer-standard.md`](report-viewer-standard.md) defers to; read it before
   touching any colour.
2. **`plugins/*/assets/tokens.css`** (12 copies, one per plugin) and
   **`docs/.vitepress/theme/tokens.css`** — byte-identical vendored copies, each a
   `[[tool.rrt.artifact_targets]]` entry in `.rrt.toml` whose `command` is a plain `cp` from
   the source. The docs copy is imported by `theme/index.js` *ahead of* `werkstoff.css`,
   specifically so the theme file can write `var(--token)` instead of restating a value —
   an `@import` straight from `tools/` was tried first and breaks the VitePress build,
   which is why the copy exists at all.
3. **`docs/.vitepress/theme/werkstoff.css`** — the theme file itself. Every `--wk-*`
   declaration it makes should be `var(--token)` against the copy in step 2, not a literal —
   but `check_design_tokens.py` only catches this where one of the four rules below actually
   matches. The rules match *property usage* (`border-radius:`, `font-family:`, a colour
   function, a bare hex), never a custom-property *declaration* by name — so
   `--wk-radius-sm: 4px;` and `--wk-transition-fast: 120ms ease;` (werkstoff.css ~114–117)
   are both literal, un-tokenised custom properties, and both are invisible to every rule:
   T-RADIUS matches only `border(-top|bottom)-(left|right)?-radius:`, not a property named
   `--wk-radius-sm`, and no rule inspects `transition:`/duration values at all. A `--wk-*`
   declaration is only ever caught indirectly, when something *using* it (e.g.
   `border-radius: var(--wk-radius-sm)`) is itself written with a literal instead.
4. **`.design/system/tokens.json`** — a DTCG-format file `plugins/matrize/scripts/retrofit_css.py`
   derives mechanically from `tokens.css` (never hand-edited: it's a build output, same
   discipline as `.rrt.toml`'s other artifact targets). Each token carries provenance under
   `$extensions."com.werkstoff.matrize"` — a card id, a reliability grade, a rights grade,
   and the edge it was derived from — because a value with no recorded source is exactly
   the kind of thing the retrofit exists to name.

This chain was retrofitted and proven by `matrize` (`matrize-preflight` then
`matrize-brief`, run 2026-09-12 against `9077ce3`); see `.design/PREFLIGHT.md` for the
grading of each reference and `.design/system/BRIEF.md` for the settled additions, the
contrast measurements behind them, and what was deliberately left unnamed (below). Neither
file is enforced by CI — they're the paper trail for why the 7 additive tokens have the
values they do, not a target `check_design_tokens.py` reads.

## The four rules, one wrong/right pair each

`scripts/ci/check_design_tokens.py` runs these over `docs/.vitepress/theme/**`
(`.css`/`.vue`/`.js`), `docs/.vitepress/config.mjs`, every `plugins/*/assets/*-viewer.html`, and
`plugins/matrize/assets/*template*.html`. Its baseline records 71 findings in 24
(path, rule) entries: T-HEX 27, T-RADIUS 33, T-FONT-FAMILY 3, T-COLOR-FN 8.

**T-HEX** — a literal hex colour in a declaration value, including inside a `var()`
fallback.

```css
/* wrong */
.verdict { border-left-color: #348ad9; }

/* right */
.verdict { border-left-color: var(--silica); }
```

A fallback counts too: `var(--accent, #348ad9)` is still a finding, because the literal is
a second source of the value and it wins silently the moment the token fails to resolve —
the "looks correct and silently does nothing" shape `CLAUDE.md` catalogues.

**T-COLOR-FN** — `rgb()`, `rgba()`, `hsl()`, `hsla()`, `hwb()`, or `oklch()` with a literal
main colour channel.

```css
/* wrong */
.swatch { background: rgba(52, 138, 217, 0.14); }

/* right */
.swatch { background: color-mix(in srgb, var(--silica) 14%, transparent); }
```

The rule is per-channel, not per-function: a literal in any **main** channel (the R/G/B or
H/S/L arguments, not the alpha) fires even when alpha is `var()` —
`rgba(52, 138, 217, var(--alpha))` is still a finding. Only when *every* main channel is
`var()` and the literal is confined to alpha — `rgba(var(--r), var(--g), var(--b), 0.5)`, or
the slash form `rgb(from var(--x) r g b / 0.5)` — is it silent; a literal alpha alone is not
a design-token concern here. A colour function whose arguments are all `var()`, main and
alpha alike, is of course also silent — the values still trace back to the source, they're
just combined at use time.

**T-FONT-FAMILY** — `font-family:`, or the `font:` shorthand, naming a family literally.

```css
/* wrong */
code, td.num { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }

/* right */
code, td.num { font-family: var(--font-mono); }
```

`var(--font-sans)`, `var(--font-mono)`, and VitePress's own `--vp-font-family-*` tokens are
all acceptable targets; a bare CSS-wide keyword (`inherit`, `initial`, `unset`) is not a
finding either, since it names no family.

**T-RADIUS** — `border-radius` or a `border-*-radius` longhand with a non-zero px literal.

```css
/* wrong */
.pill { border-radius: 4px; }
.pill { border-radius: var(--radius-sm, 4px); }  /* still wrong -- the fallback is the literal */

/* right */
.pill { border-radius: var(--radius-sm); }
```

`0`, a `var()` with no literal fallback, and a percentage (`50%`, used for circular
avatars/dots) are all exempt — none of them names a value the token scale owns.

## What is exempt, and why

- **Comments.** CSS `/* … */` and HTML `<!-- … -->`. A contrast figure quoted in prose (like
  the ones in this file) is documentation about a value, not a second declaration of it.
- **A `tokens.css` that is byte-identical to the source.** The scanned surfaces are
  `docs/.vitepress/theme/**` and the viewer/template globs above — `plugins/*/assets/tokens.css`
  (the 12 vendored plugin copies) isn't one of them, so those files are never scanned at all,
  exemption or not. The one place a `tokens.css` can actually appear in scope is
  `docs/.vitepress/theme/tokens.css`, and it is exempt only when it is byte-for-byte identical
  to `tools/design-tokens/tokens.css` — checked by comparing file contents, not by the
  filename alone. A file named `tokens.css` that has diverged (hand-written, stale, or
  otherwise different) is **not** exempt and is scanned like any other file — this is what
  keeps a hand-edited fork of the token file from becoming an unpoliced literal dump.

Nothing else is exempt. A viewer's own inline `<style>` block is not the tokens file, even
though it sits right next to the `<!--__DESIGN_TOKENS__-->` marker that fills one in — see
[`report-viewer-standard.md`](report-viewer-standard.md#design-tokens) for why the marker
and this check are two separate concerns.

## The shrink-only baseline

Findings that already exist when the check lands are recorded in
`scripts/ci/design-tokens-baseline.txt`, one line per `path`/`rule` pair with its count. The
rule has three branches, not one:

- a path carrying a finding that isn't in the baseline at all — **fail**;
- a count *above* its baseline number — **fail**, new bypasses were added;
- a count *below* its baseline number — **also fail**, with a message naming the number to
  lower it to.

That third branch is the one easy to miss: fixing code is not enough by itself. **The one
legitimate way a count goes down is fixing the findings and lowering that line in
`design-tokens-baseline.txt` to match, in the same change.** A baseline left high after the
code improved is exactly the stale-permission shape this repo already tracks for
`test/plugins/tag-releases-baseline.txt` and the `ruff.toml` per-file-ignores — a ratchet
that only holds if both sides move together. Never raise a number in the baseline, and
never add a new path to it; either means new code was written against a literal instead of
the token.

Counts are per file and per rule, not per line, so an edit to an unrelated part of a file
doesn't churn its baseline entry.

## How to fix a finding

In order of preference:

1. **Reference the token**: `var(--token-name)`.
2. **Need a translucent version of a token colour?** `color-mix(in srgb, var(--token) N%, transparent)` —
   never `rgba()` of the token's own channels re-typed as literals.

   **Except as a gradient stop, when the render must not move.** `color-mix()` computes to a
   non-legacy `color(srgb …)` value, and a gradient containing one interpolates in OKLab instead
   of sRGB. Measured on this site's hero backdrop: 84k pixels changed (max 4/255) when its two
   `rgba()` stops became `color-mix()`, and ~10k still changed with `in srgb` declared. That is
   why `werkstoff.css` keeps those two stops as commented `rgba()` literals, carried in the
   baseline. A *new* gradient has no earlier render to preserve — write it with `color-mix()`.
3. **Never add a new literal that happens to match** an existing token's value. A second
   spelling of `#348ad9` is a second source of truth the moment either one is edited alone.

## How to add a new token

Needed a value the source doesn't have a name for yet? That's what the 7 additive tokens in
this pass are worked examples of — `--accent-on-light`, `--accent-on-light-strong`,
`--rule`, `--rule-soft`, `--rule-on-light`, `--rule-soft-on-light`, and `--font-mono`, each
copied verbatim from where the docs theme or the viewers were already using it, with its
contrast measured rather than assumed (`--rule` at 3.07:1 on `--bg`, clearing the 3:1
non-text minimum; `--rule-soft` at 2.40:1, deliberately under 3:1 because it's never the
sole signal — see `tools/design-tokens/tokens.css` for the full comment on each).

1. **Append to the source**, `tools/design-tokens/tokens.css` — a new declaration in a
   second, later `:root {}` block if you want the original 50 provably untouched (that's
   the convention this pass used), with a comment stating what it's for and where its value
   was copied from.
2. **Record contrast** for a colour token with `plugins/matrize/scripts/contrast.py`
   (`contrast.py "#hex" "#hex"`, or `--css tokens.css --on "#0a0d10"` to sweep the whole
   file) and paste the measured ratio into the comment. Run
   `plugins/matrize/scripts/contrast.py --selftest` first if you haven't trusted this
   session's copy of it yet — it's checked against known published WCAG values for exactly
   the reason `CLAUDE.md` gives for verifying every instrument here.
3. **`rrt artifacts --regenerate`** (not `--snapshot` — a snapshot only records what's
   already on disk as correct; regenerate re-runs every target's actual command, including
   the `cp` to each `plugins/*/assets/tokens.css` and `docs/.vitepress/theme/tokens.css`,
   and `retrofit_css.py` to rebuild `.design/system/tokens.json`).
4. **Re-run the retrofit** — but `plugins/matrize/scripts/validate_tokens.py
   .design/system/tokens.json` cannot by itself confirm the new token isn't an orphan. No
   `LEXIKON.md` exists yet, so *every* token already fails `V-VOCAB-MISSING` (57 of them,
   one per token, exit 1) — a new token's finding is indistinguishable from the 57 already
   there. The check is inert for isolating a new token until a `matrize-name` pass produces a
   LEXIKON and gives tokens something to be validated against. What *does* isolate it today:
   run `validate_tokens.py` before adding the token, note the `V-VOCAB-MISSING` count, add the
   token, run it again — a delta of exactly +1 means the new token was picked up and nothing
   else changed; any other delta (0, or more than 1) means look again before trusting it. Also
   run `prove_retrofit.py` if a visual-diff proof is expected for the surface that now
   references it.
5. **Reference it with `var()`** wherever the literal used to be — never leave the old
   literal in place "for now."

## What stays deliberately unnamed

Three scales the retrofit found real literals for, and chose not to invent tokens for,
because — in `.design/system/BRIEF.md`'s own words — "naming a scale from literals is a
design decision this retrofit does not have the evidence to make":

- **Radius.** `--radius-sm` (4px), `--radius-control` (6px), `--radius-panel` (8px) exist.
  34 non-zero px `border-radius` literals are carried in the baseline across the theme and the
  viewers (a pre-script estimate said 26; the check's own run is the figure), at values including
  2px, 3px, 9px, and 12px. Being a multiple or fraction of an existing step is not the bar —
  arithmetically most of these are (2px is 4px/2, 12px is 3×4px or 2×6px) — and that is exactly
  why this is deliberate, not measured: naming a fourth or fifth radius step is a design
  decision about which values earn a name, and this retrofit did not have the evidence (or the
  mandate) to make it. A literal that already matches an existing token's value should be
  rewritten to it; T-RADIUS's baseline is what tracks whether that's happening. The off-scale
  values stay literal and stay in the baseline until someone actually decides on that step —
  that's not a decision this page or the CI check makes for you.
- **Font size.** `--font-size-base` (14px) is the only type token. Roughly 14 other literal
  sizes are in use. No rule inspects `font-size` at all — a new literal size today is
  invisible to `check_design_tokens.py`, not merely permitted.
- **Spacing.** The source's `--space-1..5` (4/8/12/16/20px) and the docs theme's own,
  larger `--wk-space-1..24` (4–96px) scale agree on their first four steps and diverge
  after — the docs scale has no 20px step and adds several the source doesn't. No rule
  inspects spacing either.

Treat all three as open, not covered. If a change needs one of them enforced, that's a new
rule and a new baseline in `check_design_tokens.py` — a documentation page cannot make that
call retroactively true.
