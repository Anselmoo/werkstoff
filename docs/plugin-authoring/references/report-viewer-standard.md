# Report-viewer standards for werkstoff plugins

Read this before writing or editing any `plugins/*/assets/*-viewer.html` or its
`plugins/*/scripts/build_*_html.py`.

Eight plugins ship a self-contained HTML report. They were built independently, share
exactly one thing — `tools/design-tokens/tokens.css`, vendored per plugin by
`.rrt.toml`'s `artifact_targets` — and diverge on everything else. This file is the
shared part that was never written down.

## Why this file exists at all

The colour system was settled by a cupertino-council pass in August 2026 and rebuilt all
seven viewers then in existence. That verdict was recorded **only in the commit message
of `821a14a`**. The design rationale it produced — the aerogel brand rule, measured WCAG
contrast, the CIEDE2000 CVD separation metric, the five-hue cap — lives in a 67-line
comment at the top of `tools/design-tokens/tokens.css`, linked from nothing. Read it
before touching any colour; it is the authority this file defers to.

A verdict nobody wrote down gets re-derived from scratch by the next council. That is
what happened, and it is the whole reason for this document.

## Craft vs content, same split as [`craft-standards.md`](craft-standards.md)

This file governs **how a viewer is built** — page shell, head, injection markers,
sizing, legend obligations, screenshot capture. It is deliberately silent on **what any
given viewer charts**: a Sankey vs a matrix vs a force graph is the author's call, made
from the shape of that plugin's data. `plugins/lehre/scripts/build_doctrine_html.py`'s
module docstring is the model for arguing such a choice.

## The report rules

These are the ones that matter. A viewer can satisfy every shell rule below and still be
a chart-renderer rather than a report.

### R1 — State the verdict in words

Every viewer must contain, in static markup, a sentence naming the finding the report
exists to surface. Not a noun label, and not interaction help.

`plugins/lehre/assets/doctrine-viewer.html:118` is the reference:

```html
<h2>Does the doctrine actually bite?</h2>
```

followed by a `.note` paragraph (`:120-125`) that says what an amber ribbon *means* —
"a blocking rule whose ribbon drains to amber is one everybody believes blocks and which
never denies a write."

Compare what the other seven offer in their equivalent slot: "Click a stage … to see that
stage's open gaps" (`board-viewer.html:105`), "Click a stage to see its full persisted
result" (`review-flow-viewer.html:62`), "drag a stage to reposition · drag empty space to
pan" (`stage-map-viewer.html:78`). Those tell a reader how to operate the widget. None
tells them what was found.

**The machine-checkable form is an element with `class="verdict"`** in static markup,
carrying that sentence. A question-heading answered by the panel beneath it is the usual
shape; a `.note` paragraph naming what the alarming colour means is the usual companion.
`scripts/ci/check_viewer_conformance.py` greps for the class, having first stripped
`<style>` blocks — see "What is mechanically checked" below.

**Test:** if the finding is stated in the README's alt text but not in the artifact, the
artifact fails this rule. That was true of every viewer except lehre.

### R2 — Never print the same number twice

Four viewers print integers in the subtitle and then restate them as KPI tiles ~200px
below: `board-viewer.html:129-131` vs `:326-331` (3 of 4 tiles), `burndown-viewer.html:134-135`
vs `:287-293` (2 of 5), `matrix-viewer.html:244-245` vs `:295-299` (2 of 4).

Pick one surface per number. The subtitle carries scope and provenance ("brownfield · 11
rules · 4 units · generated from `.lehre/ruleset.json`"); tiles carry findings.

### R3 — An actionable number must not look like an inert one

`.stat`, `.stat .v` and `.stat .k` are byte-identical in three files
(`board-viewer.html:75-83`, `burndown-viewer.html:31-39`, `matrix-viewer.html:186-191`) —
a shared component by copy-paste. All three render every number at `22px/600/var(--accent)`.
So confab's "Escalated" is typographically identical to its "Total passes", and nothing in
the design distinguishes a number you must act on from one that is context.

`plugins/lehre/assets/doctrine-viewer.html:36-43` is the only counter-example in the
marketplace: `.fstep.terminal` and `.fstep.leak` carry different outlines, and the leak's
value is recoloured at `:233`. Adopt that vocabulary — a tile row needs at least one class
meaning "this is the bad number".

### R4 — Colour is never the only channel

`tools/design-tokens/tokens.css` states the mandate directly, for `--status-good` /
`--status-bad` and for the `--cat-1`/`--cat-3` pair that is closest under deuteranopia
simulation (dE00 5.69): *never color alone, always pair with an icon or a label.*

A viewer therefore needs a legend that is visible **without interaction**. Two current
violations:

- `plugins/confab/assets/burndown-viewer.html:61-62` defines `.legend` and `.legend .swatch`
  and **uses neither**. Its `open`/`closed`/`escalated` status colours (`:280`) are never
  explained anywhere.
- `plugins/self-assess/assets/stage-map-viewer.html` assigns fills at `:174-178` and names
  them only in a sidebar badge after a click (`:408-410`). A reader who never clicks cannot
  learn that amber means god-module or that a dashed ring means dead-end.

A third is self-inflicted: `matrix-viewer.html:216` explains cell-colour semantics in the
sidebar placeholder, and `selectCell` destroys that text on the first click (`:466`).

Prose may substitute for swatches where it genuinely explains the encoding (lehre's `.note`
does), but silence may not.

### R5 — Height derives from content

Fixed heights that cannot grow with the data: `review-flow-viewer.html:157` `HEIGHT = 190`,
`burndown-viewer.html:69` `height: 300px`, `board-viewer.html:219` `H = 90`.

Content-derived, and correct: `doctrine-viewer.html:250`
`const H = Math.max(230, DATA.totals.rules * 24 + 100);` and
`architecture-tree-viewer.html:130` `const svgHeight = rows.length * ROW_H;`.

A panel whose height is a constant is a panel that will either clip or float in dead space.
The seven 1600×1000 screenshots taken in `821a14a` run 55–72% empty for exactly this reason.

## The shell rules

### S1 — One page archetype per data shape, declared

Three archetypes exist and all three are legitimate:

| archetype | when | current users |
|---|---|---|
| centered document | the report is read top-to-bottom | `lehre` (`.wrap`, max-width 1180), `cli-scaffold` |
| full-bleed + sticky sidebar | a selection drives a detail pane | `andon`, `confab`, `cupertino` |
| absolute canvas | the view is pannable/zoomable | `self-assess` |

`compass` is currently a fourth thing by accident — `branch-comparison-viewer.html:23`
sets `max-width: 900px` with no `margin: auto`, so content hugs the left edge. That is a
bug, not an archetype.

Whichever is chosen, the header height comes from **`var(--header-h)`**. It was a bare
`61px` literal in three files (`board-viewer.html:38,40`, `matrix-viewer.html:61`,
`review-flow-viewer.html:30,32`), defined nowhere, so a sticky sidebar's
`calc(100vh - 61px)` could silently drift from whatever the header actually measured.

### S2 — Required `<head>`

- **CSP meta, `default-src 'none'`** — `.rrt.toml:274-275` already calls this "the same
  constraint every report-viewer plugin's HTML asset needs". Present in five
  (`andon`, `cli-scaffold`, `codebase-consistency`, `compass`, `self-assess`, each at line 6);
  **absent in `lehre`, `confab`, `cupertino`**.
- **`<title>` as `<plugin> — <report noun>`**, lowercase plugin name. `lehre — doctrine map`
  is the model. Current titles are inconsistently cased and prefixed.
- **One tokens marker spelling: `<!--__DESIGN_TOKENS__-->`.** Three spellings are in use
  today — that comment form (five viewers), `/*__DESIGN_TOKENS__*/` (`cupertino`), and
  `/*__TOKENS__*/` (`confab`, `cli-scaffold`). The palette is shared; the pipeline
  delivering it is not.

### S3 — Untrusted input, two independent barriers

The builder escapes `<`, `>`, `&` on the way into the `<script>` block **and** the template
renders every string through `textContent`, never `innerHTML`.
`build_doctrine_html.py`'s `render()` and `doctrine-viewer.html:189-192` document the pairing.
Neither barrier is load-bearing alone.

### S4 — Fail visibly

All eight already do this correctly: a missing or unparseable input renders a "re-run X to
regenerate" message, never a blank page. Keep it.

## Screenshots

### C1 — Capture at content height, not a fixed viewport

Width 1600 for consistency; height = the page's own `scrollHeight`. The seven images from
`821a14a` are all 1600×1000 and mostly empty. `plugins/lehre/assets/doctrine-viewer-screenshot.jpg`
is 1600×1728 because that is where its content ends.

### C2 — The demo data must be committed

`git show --stat` across all seven original screenshot commits confirms **no demo data was
ever committed alongside any screenshot**, so none of them can be regenerated. `/analysis/`
being gitignored is part of why.

Commit the input beside the builder and cite it from the plugin README with a runnable
command — `plugins/lehre/scripts/fixtures/sample_doctrine_ruleset.json` and the block under
"The doctrine map" in `plugins/lehre/README.md` are the pattern.

Cite it. `plugins/codebase-consistency/scripts/testdata/sample_matrix.json` is committed and
referenced by nothing; an uncited fixture rots silently.

### C3 — Demo data must show the failure the plugin exists for

A clean, fully-passing dataset makes a prettier image and a useless one. lehre's fixture is
11 rules chosen so three blocking rules leak into amber "sweep + CI only" — the exact defect
the plugin was built to expose.

### C4 — Alt text describes the image, not the feature

The README alt text is the accessible substitute for the picture. Existing ones are the
right length and specificity; match them.

## What is mechanically checked, and what is not

`rrt artifacts --check --strict` verifies the **vendored copy** of `tokens.css` by hash and
size. It cannot see whether a viewer still *uses* the shell it was given: a viewer that
quietly stopped including it leaves the lock green. Per `CLAUDE.md`, that is "a guard
predicated on its own input existing".

The conformance check is therefore a separate lint,
`scripts/ci/check_viewer_conformance.py`, over `plugins/*/assets/*-viewer.html`, wired into
`.github/workflows/plugin-checks.yml` beside `scripts/ci/check-js-syntax.sh`. It decides
R1, R4, S1, S2, C1 and C2 and **deliberately does not attempt R2, R3 or R5** — a lint that
pretended to decide those would report success on prose it cannot read.

It runs every content check against the document with `<style>` blocks removed. That is
load-bearing rather than tidy: confab defines `.legend`/`.legend .swatch` and uses neither,
so a naive substring search for `legend` passes on a viewer that has none. On first run it
reported 36 violations across 8 viewers, independently reproducing findings that had been
derived by reading — CSP absent in exactly confab/cupertino/lehre, `61px` in exactly
andon/codebase-consistency/cupertino, R4 failing in exactly confab/self-assess. Three prior HTML-grep precedents
exist — `plugins/cli-scaffold/scripts/selftest.py:166-171`,
`plugins/compass/scripts/test_build_branch_comparison_html.py:106-108`,
`plugins/confab/scripts/test_build_burndown_html.py:106-113` — and **none of them runs in
CI**, which puts all three below "a fenced command in a skill" on this repo's own
enforcement table.

Only S2 and C1 are cheaply greppable. R1 through R4 are editorial and need a human or an
agent reading the rendered report.

**The lint cannot see a stale screenshot.** It checks that the JPEG exists and is 1600
wide; it has no way to know the image was rendered from an older build of the viewer
beside it. That is not hypothetical — `plugins/self-assess/assets/stage-map-viewer-screenshot.jpg`
was committed in `821a14a`, *the commit that migrated the viewer onto `tokens.css`*, and
its background pixels were `#1e1e1e`: the pre-migration `--bg`, not the `#0a0d10` the
tokens define. The image never matched the code it documented, and nothing noticed for
a year. C2 is the mitigation that actually works — if the demo data is committed and the
rebuild command is in the README, anyone can regenerate the image and diff it. Treat a
viewer change without a recapture as an unfinished change.
