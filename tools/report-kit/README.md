# report kit

Shared components for every `plugins/<name>/assets/<name>-viewer.html`: the reason a
werkstoff report shows **evidence** for each finding instead of a bare count.

| file | what it is | vendored to |
|---|---|---|
| `report-kit.css` | the `--rk-*` role layer over `tools/design-tokens/tokens.css`, dark default + light (OS or toggle) + print; header, nav, glance tiles, banners, badges, findings, tables, proof, before/after, failure panel | `plugins/<p>/assets/report-kit.css` |
| `report-kit.js` | `RK` — `h()`, `safeUrl()`, `readData()`, `fail()`, `glance()`, `proof()`, `findings()`, `table()`, `beforeAfter()`, `section()`, `init()` (theme, nav, search, deep links, print) | `plugins/<p>/assets/report-kit.js` |
| `report_kit.py` | `render(template, assets, report)` — inlines tokens, kit and the JSON data island; `--selftest` | `plugins/<p>/scripts/report_kit.py` |
| `example-viewer.html` + `example-data.json` | every component, rendered; the reference to copy from | — |

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

`capture_viewer_screenshot.py --min-figure-share 0.6` checks the figure covers at least 60 %
of a 1600 × 900 first screen.

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
