---
description: Render the divergence inventory as a module × convention consistency matrix — not a dependency graph
argument-hint: <area-dir>
---

Render `analysis/$1/consistency.json` (from `/consistency-scan`) as a
navigable **consistency matrix**: rows are modules, columns are convention
dimensions, and each cell shows which variant that module uses and how far
it sits from the eventual canonical form.

## Why a matrix, not a dependency graph

The data here is **categorical** — module × dimension → variant — not
relational. A node-link graph (call graph, topology map) answers "who
depends on whom"; that question doesn't arise for style/pattern
divergence. A matrix answers the actual question at a glance: *where* does
each module diverge, and *how much* of the area is affected by any one
dimension. It also scales better here — a graph with many convention-edge
types per pair of modules tangles quickly; a matrix just grows more
columns.

A dependency-graph view is still useful in one specific case: when
divergence clusters at team or historical-ownership boundaries (module
group A always uses variant X, group B always uses variant Y — usually
because they were written by different teams or at different times). Treat
that as an **optional secondary view** (see below), not the default.

## Build the matrix data

From `consistency.json`, derive per-module rows: for each in-scope
dimension, which variant(s) that module's files use, and the site count.
Write `analysis/$1/matrix.json`:

```json
{
  "area": "$1",
  "modules": ["billing", "shipping", "auth"],
  "dimensions": ["error-handling-style", "logging-style", "test-structure"],
  "cells": [
    { "module": "billing", "dimension": "error-handling-style", "variant": "return Result<T,E>", "sites": 41, "conformance": 1.0 },
    { "module": "shipping", "dimension": "error-handling-style", "variant": "raise + catch at boundary", "sites": 17, "conformance": 0.0 }
  ]
}
```

`conformance` is filled in only after `/consistency-canonize` has picked a
canonical variant per dimension (1.0 = matches canon, 0.0 = fully
divergent, fractional = mixed within the module). Before canonize has run,
omit the field — the map still renders, just without the "distance from
canon" color scale; render cells by variant-cluster color instead.

## Render

`analysis/$1/CONSISTENCY_MATRIX.html` — a self-contained, offline-capable,
D3/SVG-rendered consistency matrix (no external CDN dependency, matching the
plugin's air-gapped-network requirement), sharing its design tokens and
vendored D3 bundle with every other report-viewer plugin. Build it with the
plugin's own script — never hand-build this HTML inline:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/build_matrix_html.py" <repo_root> $1 \
    --template "${CLAUDE_PLUGIN_ROOT}/assets/matrix-viewer.html" \
    --d3 "${CLAUDE_PLUGIN_ROOT}/assets/inline-d3.html" \
    --tokens "${CLAUDE_PLUGIN_ROOT}/assets/tokens.css"
```

This reads only `analysis/$1/matrix.json`, written in the previous step — it
does not re-derive or estimate anything not already on disk. Writes
`analysis/$1/CONSISTENCY_MATRIX.html`.

The viewer: rows = modules (sortable by total divergence), columns =
dimensions (sortable by variant count), cell color = conformance-to-canon
once available, otherwise variant-cluster identity. Click a cell to see
its `file:line` examples in a side panel. A "worst first" sort surfaces
the modules and dimensions needing the most alignment work at the top.

## Optional secondary view — dependency clustering

Only build this when `/consistency-scan` or a human notes that divergence
seems to track team/ownership lines rather than being scattered randomly.
If so, and only then: extract a lightweight import/call graph (same
approach as a topology map, much shallower — you need module-to-module
edges, not a full call graph), color nodes by their dominant variant per
the dimension in question, and render a small force-directed or
circle-pack view showing whether divergence clusters. This is a
diagnostic aid for *why* the codebase diverged, not a required artifact —
skip it unless it's asked for or the clustering hypothesis is worth
checking.

## Present

Tell the user to open `analysis/$1/CONSISTENCY_MATRIX.html`, sort by
"most divergent," and click a cell to see examples. Suggest
`/consistency-canonize $1` next if it hasn't run yet.
