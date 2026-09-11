---
name: vorbild-emit
description: "Use to render a derived design system to a concrete target by running the plugin's committed formatter scripts against its DTCG token file — html and pdf produce the landscape sketchbook that carries the approval block, css/tailwind/scss/json/toml produce platform output. Trigger on 'emit the design system as CSS', 'produce the sketchbook PDF', 'generate the Tailwind config', 'vorbild emit'. One neutral source, N formatters: nothing here is authored per run, so the same tokens regenerate byte-stable, and prose from an R2 or R3 reference is refused rather than reproduced."
argument-hint: "--target <html|pdf|css|tailwind|scss|json|toml>"
---

Run a formatter. Do not author one at run time.

`emit` is a tool-wrapper: the formatters are committed scripts under
`${CLAUDE_PLUGIN_ROOT}/scripts/`, so emitting is deterministic and free. Authoring a new
formatter is a change to this plugin, reviewed like any other — not something that
happens invisibly inside a run and produces slightly different output each time.

That determinism is what makes `vorbild-retrofit`'s zero-visual-diff proof possible at
all. A formatter that re-decides its output per run cannot prove equivalence with
anything.

## Input gate

Requires `<root>/system/tokens.json`. If it is absent, say which phase produces it
(`decode` + `name`, or `retrofit`) and stop.

If a `spread` choice record exists and is unanswered, the `PreToolUse` guard denies the
write — so record the choice first. That is a refusal, not a warning, and reaching for
`VORBILD_DISABLE_GUARD=1` to get past it defeats the phase.

## The rights refusal

> Reference prose from an R2 or R3 source is never written into an emitted artefact.

Values, measured facts, and rules restated in this system's own words are fine. The
source's sentences, illustrations and assets are not. When a formatter would need to
reproduce reference text to be useful, the design is wrong — cite and link instead.

## Targets

**`html`** is the reference formatter and simultaneously the portfolio: the landscape
sketchbook, one building block per page, marginal callouts carrying purpose, rule and
anti-rule, and the approval block naming the decision-maker and the gate criteria.

**`pdf`** renders that HTML through headless Chrome `--print-to-pdf`, honouring
`@page { size: … landscape }`.

Never wkhtmltopdf. Its Qt WebKit engine renders `@font-face` spans **blank** — text
disappears entirely while spaces are preserved — does not interleave multi-page CSS Grid
columns, silently ignores header/footer flags on unpatched builds, and has no useful
`--zoom` when the CSS uses physical units. Those are documented failures, not
speculation, and re-acquiring them would be a choice.

**Verify the render, do not trust it.** After producing a PDF: extract its text
(`pdftotext -layout`) and grep for strings that must be present. A silently blanked span
looks fine in a page count and is invisible in a thumbnail. Also confirm the page count
and reading order.

**`css`, `tailwind`, `scss`, `json`, `toml`** are platform output. None of them is ever
an input: if a change needs making, it is made in `tokens.json` and re-emitted. A hand
edit to emitted output is lost on the next run, and worse, it makes the source untrue.

## Report

Name the target, the formatter script that ran, the output path, and — for `pdf` — the
verification that actually executed, with its result. If a verification step did not
run, say so rather than implying it passed.
