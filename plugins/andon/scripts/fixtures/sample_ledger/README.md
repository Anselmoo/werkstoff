# `sample_ledger` — the committed demo ledger behind `assets/board-viewer-screenshot.jpg`

A real OKF ledger directory (`log.md` + `stages/` + `gaps/` + `evidence/`), written in the
schema `andon_core.py` actually **reads**: `status`, `stage`, `kind`, `blast_radius`,
`wire`, `verdict`, `tier` and `non_overridable` are first-class frontmatter keys here, not
values buried in a `tags:` array. A ledger that encodes them only as tags renders an empty
board — `render_board()` looks at `fields`, never at `tags`.

It is deliberately **not** a clean, fully-passing stream. The five-stage feature pipeline
it describes is stopped:

| wire | evidence | how it draws |
|---|---|---|
| `ingest->normalize` | strategy `f` property proof, then strategy `b` numerical V&V — both green | solid green |
| `normalize->enrich` | strategy `a` tribunal, verdict `unknown` (hung) | solid amber — unproven |
| `enrich->score` | strategy `e` structural index, **tier 1, `non_overridable: true`**, verdict red | solid red + hold banner |
| `score->publish` | no evidence doc exists | dashed — no evidence yet |

Seven gaps are open across four of the five stages (`publish` has none, so one stage
renders without a badge), spanning all three `kind`s and all three `blast_radius`
values. `log.md` carries seven passes across two cycles plus a sub-cycle entry recording
`enrich->score` reopened three times, which is what makes it the board's active
constraint.

Regenerate the HTML with the command under "The board, as an HTML report" in the plugin
README.
