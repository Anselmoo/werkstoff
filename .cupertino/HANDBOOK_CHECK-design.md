# Handbook check — design

Checked against `.cupertino/design-handbook.md`'s 6 dimensions. 18 finding(s) survived independent re-verification (7 mechanical, 11 needing design judgment).

**Resolved since this report** (not re-run through the check workflow; noted by hand): 10/12 mechanical findings applied via `cupertino-handbook-fix`; the remaining 2 (`board-viewer.html:270` --ferria-deep badge text, and the `ui-missing-alt` test-data-management finding tracked separately) were blocked by the remediator for exceeding its single-file-line scope and applied directly instead. `board-viewer.html`'s `RADIUS_COLORS['shared-state-visible']` now uses `var(--ferria)`.

Both of the two remaining non-mechanical findings are now also resolved, via a `cupertino-council` pass (Council Brief → Tension Log, both tensions resolved as Usability):
- `matrix-viewer.html:665` (accessibility-baseline) — the legend now dynamically enumerates every distinct variant actually present, sorted by frequency, pairing each hue to its label; no longer requires clicking every cell to identify a variant.
- `review-flow-viewer.html:133` (empty-and-error-states) — the nine-entry fabricated demo dataset was deleted outright; missing/invalid data now shows the same `#err`-panel-then-throw pattern as board-viewer.html/matrix-viewer.html/doctrine-viewer.html, naming `cupertino-review` as the regenerate command. Verified visually: opening the raw template shows the error panel with no leaked fake stage data and no console errors.

All 9 `spacing-and-layout-grid` findings are now resolved, via a second `cupertino-council` pass on the policy question (not per-value — 60+ declarations across 9 files all reduced to two decisions: mid-scale tie-break direction, and how to handle 40px vs. the scale's 20px ceiling). Both tensions resolved as Usability: ties round up (favor more room over less); 40px becomes `calc(var(--space-5) * 2)` rather than lossily collapsing to a single token, preserving the visual weight of a real section break. Applied across `board-viewer.html`, `architecture-tree-viewer.html`, `matrix-viewer.html`, `branch-comparison-viewer.html`, `burndown-viewer.html`, `review-flow-viewer.html`, `doctrine-viewer.html`, `stage-map-viewer.html`, and `docs/.vitepress/theme/werkstoff.css`'s `.hz-*` rules (rem-based, mapped onto the `--wk-space-*` scale by the same policy). Verified: brace-balance check on every edited `<style>` block, `node --check` on every edited inline script, `npm run docs:build` + `docs_ux_audit.py` (0 findings), and a live computed-style check confirming `.hz-card` now resolves to `16px 24px`.

**Design domain: 18/18 findings resolved.**

| Severity | Mechanical | Dimension | Location | Title |
|---|---|---|---|---|
| High | yes | color-and-contrast | `plugins/andon/assets/board-viewer.html:270` | --ferria-deep used as text color for the 'shared-state-visible' badge label |
| High | no | empty-and-error-states | `plugins/cupertino/assets/review-flow-viewer.html:133` | Missing data silently falls back to fabricated demo content instead of erroring |
| High | yes | color-and-contrast | `plugins/lehre/assets/doctrine-viewer.html:352` | -deep tokens used as Sankey node fill (a standalone chart mark), not a decorative fill/border |
| High | yes | color-and-contrast | `plugins/lehre/assets/doctrine-viewer.html:85` | --ferria-deep used as the stroke of a blocked-dependency edge (a standalone chart mark) |
| High | yes | empty-and-error-states | `plugins/lehre/assets/doctrine-viewer.html:520` | Missing-data path shows no regeneration command and never throws |
| High | yes | typography-system | `plugins/self-assess/assets/stage-map-viewer.html:22` | Base font set via hardcoded literal instead of design tokens |
| Medium | no | accessibility-baseline | `/Users/hahn/LocalDocuments/GitHub_Forks/werkstoff/.claude/worktrees/angry-mcclintock-d4cd76/plugins/codebase-consistency/assets/matrix-viewer.html:665` | Pre-canonization grid cells encode variant identity by hashed hue alone, with no visible-without-interaction legend pairing a specific color to a specific variant name |
| Medium | no | spacing-and-layout-grid | `docs/.vitepress/theme/werkstoff.css:813` | Hazard-card block spacing uses rem values off the documented --wk-space-* scale |
| Medium | no | spacing-and-layout-grid | `plugins/andon/assets/board-viewer.html:35` | Off-scale px literals used for margin/padding/gap (not 4/8/12/16/20) |
| Medium | no | spacing-and-layout-grid | `plugins/codebase-consistency/assets/matrix-viewer.html:54` | Off-scale px literals used for margin/padding/gap (not 4/8/12/16/20) |
| Medium | yes | typography-system | `plugins/codebase-consistency/assets/matrix-viewer.html:11` | Base body rule omits line-height token entirely |
| Medium | no | spacing-and-layout-grid | `plugins/confab/assets/burndown-viewer.html:24` | Off-scale px literals used for margin/padding/gap (not 4/8/12/16/20) |
| Medium | yes | typography-system | `plugins/confab/assets/burndown-viewer.html:11` | Base body rule omits line-height token entirely |
| Low | no | spacing-and-layout-grid | `plugins/cli-scaffold/assets/architecture-tree-viewer.html:31` | Off-scale px literals used for margin/padding/gap (not 4/8/12/16/20) |
| Low | no | spacing-and-layout-grid | `plugins/compass/assets/branch-comparison-viewer.html:35` | Off-scale px literals used for margin/padding (not 4/8/12/16/20) |
| Low | no | spacing-and-layout-grid | `plugins/cupertino/assets/review-flow-viewer.html:59` | Off-scale px literals used for margin/padding/gap (not 4/8/12/16/20) |
| Low | no | spacing-and-layout-grid | `plugins/lehre/assets/doctrine-viewer.html:41` | Off-scale px literals used for margin/padding/gap (not 4/8/12/16/20) |
| Low | no | spacing-and-layout-grid | `plugins/self-assess/assets/stage-map-viewer.html:35` | Off-scale px literals used for margin/padding/gap (not 4/8/12/16/20) |

## Details

### `/Users/hahn/LocalDocuments/GitHub_Forks/werkstoff/.claude/worktrees/angry-mcclintock-d4cd76/plugins/codebase-consistency/assets/matrix-viewer.html:665` — Pre-canonization grid cells encode variant identity by hashed hue alone, with no visible-without-interaction legend pairing a specific color to a specific variant name

**Dimension:** accessibility-baseline · **Severity:** Medium · **Mechanical:** False

**Evidence:** `.attr('fill', d => { if (!d.c) return 'url(#emptyHatch)'; return hasConformance && typeof d.c.conformance === 'number' ? colorForConformance(d.c.conformance) : colorForVariant(d.c.variant || '?'); })` (line 665-669) draws each cell's fill from `colorForVariant()`, an 8-color hash (`PALETTE`, line 381) with no accompanying text on the cell itself -- the only visible text inside a cell is the site count (`.text(d => d.c.sites)`, line 684), not the variant name. When `hasConformance` is false, `renderLegend()`'s only entry for this mode is a single generic disclaimer with an empty-string swatch: `legend.appendChild(legendItem('', 'colours show variant identity, one hue per distinct variant — no ranking implied'));` (line 755). That legend never pairs any of the 8 actual hex colors with the variant name each represents; the real mapping is revealed only after clicking a cell, when `selectCell()` writes `cell.variant` into the sidebar (lines 705, 716-717). So in this mode a reader cannot tell, without clicking every cell, which colored cells share a variant or what that variant is called -- color is the only visible-without-interaction channel distinguishing categories, unlike the conformance-mode legend directly above it (lines 745-753), which does name each of --status-good/--status-warn/--status-bad explicitly.

**Suggested fix:** In the no-conformance branch, either print the variant name (or a short stable identifier) as visible text inside each cell alongside the site count, or build the legend dynamically by enumerating the distinct variants actually present in MATRIX.cells and pairing each with its resolved colorForVariant() swatch and label, the same way renderLegend() already does for the conformance-scale branch.

### `plugins/andon/assets/board-viewer.html:270` — --ferria-deep used as text color for the 'shared-state-visible' badge label

**Dimension:** color-and-contrast · **Severity:** High · **Mechanical:** True

**Evidence:** Line 230: `'shared-state-visible': 'var(--ferria-deep)',` in RADIUS_COLORS; consumed at line 270: `'<span class="badge" style="color:' + radiusColor + '">' + escapeHtml(radiusLabel) + '</span>'` where radiusLabel is the literal readable text "shared state visible". Measured contrast of --ferria-deep (#82260f) against --bg (#0a0d10) is 2.07:1, and 1.87:1 against --panel (#141a1f) which is the badge's actual backdrop -- both far below the rule's 4.5:1 text floor. Per tokens.css's own comment, no *-deep step other than --samaria-deep even reaches 3:1, and even that exception is declared fill/border-only, never text.

**Suggested fix:** Swap RADIUS_COLORS['shared-state-visible'] from var(--ferria-deep) to var(--ferria) (4.08:1 on --bg, 3.67:1 on --panel -- both above the mark floor, and closer to 4.5 for text) or var(--ferria-light), matching the light/base/deep ramp already used for the other two entries in the same map ('local+reversible': ferria-light, 'hard-to-reverse': ferria).

### `plugins/lehre/assets/doctrine-viewer.html:352` — -deep tokens used as Sankey node fill (a standalone chart mark), not a decorative fill/border

**Dimension:** color-and-contrast · **Severity:** High · **Mechanical:** True

**Evidence:** NODE_COLOR (lines 173-175) maps three provenance categories to var(--chromia-deep), var(--silica-deep), var(--neodymia-deep); line 352 applies the mapped value as `fill:` on the Sankey diagram's node `<rect>` -- the graphical mark that IS the category encoding, sized by count. Measured contrast: chromia-deep 2.47:1, silica-deep 2.74:1, neodymia-deep 2.74:1 against --bg (lower still against --panel, ~2.2-2.5:1) -- all below the 3:1 mark floor, and tokens.css states even the one -deep step that numerically clears 3:1 (--samaria-deep) is still 'a fill/border token by role', never mark-eligible, so a rect that IS the chart's data-bearing mark cannot legitimately use any -deep step.

**Suggested fix:** Replace the three -deep entries in NODE_COLOR with their base steps (var(--chromia), var(--silica), var(--neodymia)), which already clear 3:1 (4.46-4.95:1) and are the mark-eligible tier the rest of this file uses for OUTCOME_COLOR and severity nodes.

### `plugins/lehre/assets/doctrine-viewer.html:85` — --ferria-deep used as the stroke of a blocked-dependency edge (a standalone chart mark)

**Dimension:** color-and-contrast · **Severity:** High · **Mechanical:** True

**Evidence:** .uedge.blocked { stroke: var(--ferria-deep); stroke-dasharray: 4 3; } -- the stroke is the entire visible content of this SVG path (a directed edge in the build-order DAG marking a blocked dependency), i.e. a lone chart mark, not a box border. Measured contrast of --ferria-deep is 2.07:1 against --bg and 1.87:1 against --panel (the panel the SVG sits in) -- below the 3:1 non-text/mark floor documented in tokens.css.

**Suggested fix:** Change stroke: var(--ferria-deep) to stroke: var(--ferria) (4.08:1 on --bg, 3.67:1 on --panel, clearing the mark floor) while keeping the stroke-dasharray as the redundant non-color channel already present.

### `plugins/andon/assets/board-viewer.html:35` — Off-scale px literals used for margin/padding/gap (not 4/8/12/16/20)

**Dimension:** spacing-and-layout-grid · **Severity:** Medium · **Mechanical:** False

**Evidence:** Line 35: `padding: 18px;` | Line 42: `margin: 0 0 10px;` | Line 43: `margin-top: 40px;` | Line 48: `padding: 1px 6px;` | Line 70: `padding: 14px 16px;` | Line 74: `gap: 14px;` | Line 79: `padding: 12px 18px;` | Line 83: `margin-top: 2px;` | Line 98: `gap: 14px; margin-top: 10px;` | Line 99: `margin-right: 5px;` — none of 18, 10, 40, 1, 6, 14, 2, 5 are members of the plugin-viewer spacing scale (4/8/12/16/20px) defined by tools/design-tokens/tokens.css's `--space-*` tokens, and these are hardcoded px rather than `var(--space-N)`.

**Suggested fix:** Replace each off-scale literal with the nearest `--space-*` token (e.g. 18px->16px or 20px, 10px->8px or 12px, 40px-> a multiple of the scale, 14px->12px or 16px, 1px/2px/5px/6px -> 4px or 8px), choosing per-instance based on the intended visual density rather than auto-rounding blindly.

### `plugins/cli-scaffold/assets/architecture-tree-viewer.html:31` — Off-scale px literals used for margin/padding/gap (not 4/8/12/16/20)

**Dimension:** spacing-and-layout-grid · **Severity:** Low · **Mechanical:** False

**Evidence:** Line 31: `margin-bottom: 2px;` | Line 50: `padding: 1px 6px;` | Line 61: `gap: 6px;` — 2, 1, and 6 are not members of the `--space-*` scale (4/8/12/16/20px).

**Suggested fix:** Round to the nearest scale token: 2px/1px -> `var(--space-1)` (4px) or accept 0 where it's a hairline; 6px -> `var(--space-2)` (8px), reviewing each spot visually.

### `plugins/codebase-consistency/assets/matrix-viewer.html:54` — Off-scale px literals used for margin/padding/gap (not 4/8/12/16/20)

**Dimension:** spacing-and-layout-grid · **Severity:** Medium · **Mechanical:** False

**Evidence:** Line 54: `padding: 6px 10px;` | Line 63: `padding: 6px 8px;` | Line 97: `padding: 0 10px;` | Line 127: `padding: 4px 10px;` | Line 167: `padding: 18px;` | Line 183: `padding: 6px 0;` | Line 193: `padding: 8px 10px;` | Line 203: `margin-top: 40px;` | Line 207: `gap: 14px;` | Line 208: `padding: 10px 20px;` | Line 220: `margin-right: 5px;` | Line 225: `padding: 14px 16px;` | Line 231: `margin: 0 0 6px;` | Line 235: `margin-top: 18px;` | Line 239: `gap: 14px; padding: 0 20px 14px;` | Line 242: `padding: 12px 18px;` | Line 245: `margin-top: 2px;` | Line 254: `margin-left: 6px;` | Line 255: `padding: 0 5px;` — 6, 10, 18, 40, 14, 5, 2 are not scale members (4/8/12/16/20px).

**Suggested fix:** Migrate each literal to the nearest `--space-*` token consistently with the file's existing `var(--space-N)` usage elsewhere (e.g. lines 23, 31, 47, 86).

### `plugins/compass/assets/branch-comparison-viewer.html:35` — Off-scale px literals used for margin/padding (not 4/8/12/16/20)

**Dimension:** spacing-and-layout-grid · **Severity:** Low · **Mechanical:** False

**Evidence:** Line 35: `margin-right: 5px;` | Line 52: `padding: 1px 5px;` — 5 and 1 are not members of the `--space-*` scale (4/8/12/16/20px).

**Suggested fix:** Replace 5px with `var(--space-1)` (4px) or `var(--space-2)` (8px) and 1px with 0/`var(--space-1)`, whichever preserves the intended visual density.

### `plugins/confab/assets/burndown-viewer.html:24` — Off-scale px literals used for margin/padding/gap (not 4/8/12/16/20)

**Dimension:** spacing-and-layout-grid · **Severity:** Medium · **Mechanical:** False

**Evidence:** Line 24: `padding: 6px 14px;` | Line 29: `gap: 14px;` | Line 34: `padding: 12px 18px;` | Line 38: `margin-top: 2px;` | Line 86: `gap: 5px;` | Line 95: `margin: 6px 0;` | Line 111: `margin: 0 0 10px;` | Line 112: `margin-top: 40px;` | Line 115: `margin-top: 2px;` | Line 118: `padding: 5px 7px;` — 6, 14, 18, 2, 5, 10, 40, 7 are not members of the `--space-*` scale (4/8/12/16/20px).

**Suggested fix:** Round each literal to the nearest `--space-*` token (e.g. 14px->16px or 12px, 18px->16px or 20px, 40px-> a multiple of the scale, 5px/6px/7px->4px or 8px, 10px->8px or 12px), reviewing per-instance.

### `plugins/cupertino/assets/review-flow-viewer.html:59` — Off-scale px literals used for margin/padding/gap (not 4/8/12/16/20)

**Dimension:** spacing-and-layout-grid · **Severity:** Low · **Mechanical:** False

**Evidence:** Line 59: `padding: 2px 8px;` | Line 71: `padding: 6px 0;` | Line 77: `padding: 0 0 6px;` | Line 93: `gap: 14px;` | Line 94: `margin-right: 5px;` — 2, 6, 14, 5 are not members of the `--space-*` scale (4/8/12/16/20px).

**Suggested fix:** Replace with the nearest `--space-*` token (2px/6px->4px or 8px, 14px->12px or 16px, 5px->4px or 8px), matching the file's existing token usage (e.g. lines 19, 20, 23, 31, 38).

### `plugins/lehre/assets/doctrine-viewer.html:41` — Off-scale px literals used for margin/padding/gap (not 4/8/12/16/20)

**Dimension:** spacing-and-layout-grid · **Severity:** Low · **Mechanical:** False

**Evidence:** Line 41: `gap: 2px;` | Line 47: `margin-top: 2px;` | Line 89: `padding: 6px 8px;` | Line 94: `padding: 1px 7px;` | Line 110: `padding: 6px 10px;` | Line 253: `margin-left:6px` (inline style string) — 2, 6, 1, 7, 10 are not members of the `--space-*` scale (4/8/12/16/20px).

**Suggested fix:** Round each literal to the nearest `--space-*` token (2px/1px->4px, 6px/7px->8px, 10px->8px or 12px), including the inline `margin-left:6px` string at line 253.

### `plugins/self-assess/assets/stage-map-viewer.html:35` — Off-scale px literals used for margin/padding/gap (not 4/8/12/16/20)

**Dimension:** spacing-and-layout-grid · **Severity:** Low · **Mechanical:** False

**Evidence:** Line 35: `padding: 10px 12px;` | Line 36: `margin-bottom: 2px;` | Line 37: `margin-bottom: 5px;` | Line 47: `margin-bottom: 6px;` | Line 49: `gap: 6px;` | Line 55: `margin-right: -3px;` | Line 56: `padding: 6px 8px;` | Line 61: `padding: 4px 6px;` | Line 69: `margin: 2px 0 10px;` | Line 73: `padding: 2px 0;` | Line 78: `padding: 1px 7px;` — 10, 2, 5, 6, 3, 1, 7 are not members of the `--space-*` scale (4/8/12/16/20px). This file has no `var(--space-*)` usage at all — every spacing value is a hand-picked literal.

**Suggested fix:** Introduce `var(--space-*)` tokens for this viewer's margins/paddings/gaps and round each literal to the nearest scale member, reviewing tight badge/legend paddings individually.

### `docs/.vitepress/theme/werkstoff.css:813` — Hazard-card block spacing uses rem values off the documented --wk-space-* scale

**Dimension:** spacing-and-layout-grid · **Severity:** Medium · **Mechanical:** False

**Evidence:** The file's own "VERTICAL RHYTHM" comment (line ~283) states 'Every value below is a member; a value that is not a member is a bug' for the `--wk-space-*` scale (4/8/12/16/24/32/48/64/96px). The later '.hz-*' hazard-card rules (lines 802-865) use raw rem literals that do not reduce to scale members at the site's 16px root: line 813 `padding: 1rem 1.25rem;` (1.25rem = 20px, not a --wk-space-* member); line 821 `margin-bottom: 0.6rem;` (9.6px); line 832 `padding: 0.1rem 0.5rem;` (1.6px); line 849 `padding: 0.6rem 0 0;` (9.6px); line 854 `margin-top: 0.6rem;` (9.6px); line 864 `margin: 0 0 0.3rem;` (4.8px).

**Suggested fix:** Replace the rem literals with the `--wk-space-*` tokens expressed in rem/px equivalents (e.g. 0.6rem -> var(--wk-space-2) 8px or var(--wk-space-3) 12px, 1.25rem -> var(--wk-space-4) 16px or var(--wk-space-6) 24px, 0.3rem/0.1rem -> var(--wk-space-1) 4px), choosing per-instance to preserve the hazard cards' intended density.

### `plugins/self-assess/assets/stage-map-viewer.html:22` — Base font set via hardcoded literal instead of design tokens

**Dimension:** typography-system · **Severity:** High · **Mechanical:** True

**Evidence:** html, body { height: 100%; overflow: hidden; background: var(--bg);
    color: var(--text); font: 14px/1.45 system-ui, sans-serif; }

**Suggested fix:** Replace `font: 14px/1.45 system-ui, sans-serif;` with `font: var(--font-size-base)/var(--line-height-base) var(--font-sans);` to match the tokens vendored at plugins/self-assess/assets/tokens.css:144-146 (which already define 14px / 1.45 / the same font stack) instead of re-hardcoding those exact values.

### `plugins/confab/assets/burndown-viewer.html:11` — Base body rule omits line-height token entirely

**Dimension:** typography-system · **Severity:** Medium · **Mechanical:** True

**Evidence:** body {
    margin: 0;
    background: var(--bg);
    color: var(--text);
    font-family: var(--font-sans);
    font-size: var(--font-size-base);
  }

**Suggested fix:** Add `line-height: var(--line-height-base);` to the body rule so all three base typography properties (font-family, font-size, line-height) come from the shared tokens, matching the pattern used in plugins/andon/assets/board-viewer.html:15-17 and plugins/cupertino/assets/review-flow-viewer.html:15-17.

### `plugins/codebase-consistency/assets/matrix-viewer.html:11` — Base body rule omits line-height token entirely

**Dimension:** typography-system · **Severity:** Medium · **Mechanical:** True

**Evidence:** body {
    margin: 0;
    background: var(--bg);
    color: var(--text);
    font-family: var(--font-sans);
    font-size: var(--font-size-base);
  }

**Suggested fix:** Add `line-height: var(--line-height-base);` to the body rule so the base font-family, font-size, and line-height are all sourced from the shared tokens, matching the pattern used in plugins/andon/assets/board-viewer.html:15-17 and plugins/lehre/assets/doctrine-viewer.html:13-14.

### `plugins/lehre/assets/doctrine-viewer.html:520` — Missing-data path shows no regeneration command and never throws

**Dimension:** empty-and-error-states · **Severity:** High · **Mechanical:** True

**Evidence:** (function () {
  if (!DATA) {
    const p = document.createElement("p");
    p.className = "empty";
    p.appendChild(txt("No doctrine data was injected into this template."));
    document.querySelector(".wrap").appendChild(p);
    return;
  }
  ...
})();

**Suggested fix:** Match the pattern used by every other viewer in this repo (e.g. board-viewer.html, matrix-viewer.html): change the message to name the exact regenerate command, e.g. 'No doctrine data found in this file.<br>Re-run <code>lehre-status</code> to regenerate it.', and replace the bare `return;` with `throw new Error('no data');` so rendering halts via a thrown error rather than a quiet function return.

### `plugins/cupertino/assets/review-flow-viewer.html:133` — Missing data silently falls back to fabricated demo content instead of erroring

**Dimension:** empty-and-error-states · **Severity:** High · **Mechanical:** False

**Evidence:** const FLOW_DATA_RAW = /*__FLOW_DATA__*/ null;

const FLOW = FLOW_DATA_RAW || {
  source: "(fallback demo — no run was read)",
  stages: [ ... nine hardcoded fake stage entries ... ],
};
...
document.getElementById('subtitle').textContent =
  (FLOW_DATA_RAW
    ? ...
    : 'no data — template opened directly, so no run is described below');

**Suggested fix:** When FLOW_DATA_RAW is missing/invalid, do not substitute fabricated demo stage data and continue rendering a full chart. Instead render a visible error panel (as board-viewer.html / matrix-viewer.html do) naming the exact command to regenerate the data — e.g. 're-run the cupertino-review skill to regenerate this file' — hide the flow/sidebar/legend, and `throw new Error('no data')` to halt further rendering. This requires removing/reworking the demo-fallback design, so it is not a pure mechanical rewrite.
