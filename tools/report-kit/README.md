# report kit

Shared components for every `plugins/<name>/assets/<name>-viewer.html`: the reason a
werkstoff report shows **evidence** for each finding instead of a bare count.

| file | what it is | vendored to |
|---|---|---|
| `report-kit.css` | the `--rk-*` role layer over `tools/design-tokens/tokens.css`, dark default + light (OS or toggle) + print; header, nav, glance tiles, banners, badges, findings, tables, proof, before/after, failure panel | `plugins/<p>/assets/report-kit.css` |
| `report-kit.js` | `RK` — `h()`, `safeUrl()`, `readData()`, `fail()`, `glance()`, `proof()`, `findings()`, `table()`, `beforeAfter()`, `section()`, `init()` (theme, nav, search, deep links, print) | `plugins/<p>/assets/report-kit.js` |
| `report_kit.py` | `render(template, assets, report)` — inlines tokens, kit and the JSON data island; `--selftest` | `plugins/<p>/scripts/report_kit.py` |
| `example-viewer.html` + `example-data.json` | every component, plus the R9 stage (a figure drawn from the stage's size, HUD with verdict and stats, floating legend, hint, a drawer opened by clicking a mark, a tooltip on hover); the reference to copy from | — |

Edit here, never a vendored copy, then `rrt artifacts --regenerate`.

## Figure first (R9)

A viewer leads with its figure. The template carries a static stage skeleton:

```html
<section class="rk-stage" id="rk-stage" aria-label="the figure, in words">
  <div class="rk-hud"><p class="verdict">…</p><dl class="rk-hud-stats"></dl></div>
  <div class="rk-figure" id="rk-figure" data-rk-figure></div>
  <div class="legend rk-legend-float">…</div>
  <aside class="rk-drawer" id="rk-drawer" hidden aria-label="Details"></aside>
</section>
```

and the page script drives it:

```js
const S = RK.stage();
S.stats([{ label: "Diverging", value: "4", bad: true }]);
S.onResize((w, h) => draw(w, h));                 // fill the figure; redraw on resize
mark.addEventListener("click", () => S.open(title, subtitle, RK.value(detail)));
mark.addEventListener("mouseenter", (e) => S.tip.show(e, title, summary));
S.onTheme(() => S.redraw());                       // colours re-read on a theme switch
S.onClose(() => clearSelection());
const { top, bottom } = S.insets();                // room the HUD and legend take
```

`capture_viewer_screenshot.py --min-ink-share 0.55` checks that what the figure DRAWS spans at
least 55 % of the 1600 × 900 first screen (overlays masked, the open drawer subtracted) — the
figure's box is not the figure. `scripts/ci/regen_viewer_screenshots.py` rebuilds and measures
every viewer from its committed demo data.

The HUD is a caption: `.verdict` is clamped to two lines and `stage()` adds a *more* button
that opens the whole sentence in the drawer; `stats()` renders one row of chips. Keep the
floating legend to one row of short labels and put each mark's long explanation in a `title`.

Deep links, focus and search are the kit's, so every viewer behaves the same way:

- `RK.hashId(prefix?)` reads the fragment, decoded, or `null` when it is malformed. Never call
  `decodeURIComponent(location.hash)` yourself, because one stray `%` throws and leaves the figure blank.
- A hash that names an item the figure selects: the viewer selects it and calls `RK.claimHash()`,
  and the page stays at the top with the drawer open. The kit opens and scrolls to any other hash
  (`#sec-*`, a card below).
- Tag every clickable mark with `data-rk-key` (or `RK.mark(el, key, text)`). The drawer hands focus
  back to that mark after a redraw, and the header search dims marks that do not match. The kit puts
  the match count beside the search box.
- `RK.fail()` on a stage page replaces the HUD verdict, so the failure is on the first screen.
- Below 860 px the drawer does not open on load. Overlays are bounded by the figure column
  (`--rk-open-w`), and the hint moves out of the way of the legend.
- A status word in text uses `--rk-ok-text` / `--rk-bad-text` / `--rk-warn-text`, never the
  mark hues. `check_contrast.py` (and its `--selftest`) holds every text role at 4.5:1 or above
  on every surface in both themes.
- `check_viewer_behaviour.py` builds every viewer state from demo data and runs
  `viewer_behaviour.js` under Playwright, which checks these rules at five viewport sizes in
  both themes.

## Render the example

```bash
python3 tools/report-kit/report_kit.py --template tools/report-kit/example-viewer.html \
  --data tools/report-kit/example-data.json --tokens tools/design-tokens/tokens.css --out /tmp/rk-example.html
python3 scripts/ci/capture_viewer_screenshot.py /tmp/rk-example.html /tmp/rk-example.png
```

## The contract the kit keeps

- **Two barriers (S3).** `report_kit.py` escapes `< > &` in the JSON island; `report-kit.js`
  builds DOM only through `createTextNode`/`textContent`, drops `on*` attributes, and passes
  every `href`/`src` through an allow-list `safeUrl()` that fails closed (`#`, http(s),
  mailto, relative; `data:image/*` for `src` only).
- **Fail visibly (S4).** `RK.readData(rerunCommand)` renders a failure that names the
  command when the island is missing or unparseable.
- **Colour is the third channel (R4).** Every badge and banner carries a word and a glyph.
- **CSP unchanged.** `default-src 'none'`; everything is inline; images are data URIs.
- **Evidence (R6), drill-down (R7), navigable (R8)** — see
  `docs/plugin-authoring/references/report-viewer-standard.md`'s content tier.
  `nacharbeit_lint.py`'s `A-REPORT-KIT` checks a viewer adopted the kit.

## Credit

The page structure (glance first, a proof block with *What this does not prove* and
*Waiting for a person*, a JSON data island, the `h()`/`safeUrl()` safety core, a section
nav that collapses to a `<select>`, the dual dark-mode block) is adapted from
`anthropics/claude-plugins-official`'s `code-modernization` plugin
(`assets/report-template.html`, `assets/topology-viewer.html`), Apache-2.0. Nothing was
copied verbatim; the code here was written for werkstoff's tokens and standard.
