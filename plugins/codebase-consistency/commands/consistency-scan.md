---
description: Inventory internal pattern/style/architecture divergence across the area — excludes documented conventions and version-deprecated idioms, which are out of scope
argument-hint: <area-dir> [convention-pattern]
---

Build an inventory of **undocumented, non-deprecated divergence** in `$1` —
places where the codebase itself contains two or more different-but-valid
ways of doing the same thing, and nothing on record says which one is
correct.

**Scope discipline — read this before dispatching anything.** This command
is deliberately narrower than a general code-quality audit:

- A convention documented in `CLAUDE.md`, `house-rules.md`, a linter config,
  or similar is **not this command's job** — checking compliance against a
  documented rule belongs to a conventions auditor (e.g. `self-assess`'s
  `convention-auditor`, if installed). If scanning surfaces a documented
  rule with live violations, report it in one line and move on; do not
  build a Pattern Card for it.
- An idiom made obsolete by the language/framework version this codebase
  actually targets is **not this command's job** either — that is
  version-driven modernization (e.g. `self-assess`'s `idiom-auditor`).
  `codebase-consistency` only cares about variants that are **all still
  valid** in the targeted version; if one variant is simply outdated for
  the declared version, that is a modernization finding, not a
  consistency finding.
- What's left, and what this command exists for: **N ≥ 2 variants, all
  valid, all currently in use, none documented as the standard.** That is
  the entire scope.

If a `[convention-pattern]` was given (`$2`), scope the scan to dimensions
matching it (e.g. `error-handling`, `docstrings`); otherwise cover the
default dimension set below.

## Default convention dimensions

Adapt to the detected stack (Check 1 from `/consistency-preflight`), but
start from: error-handling shape, logging style, docstring/comment format,
module/file layout, import ordering and grouping, naming conventions
(functions, files, test files), test structure (arrange/act/assert layout,
fixture style, naming), configuration/constants placement, and
public-API surface shape (return types, parameter ordering, optional-arg
conventions).

## Method A — Workflow orchestration (preferred when available)

If the **Workflow tool** is available in this session, use it — this
command invocation is your authorization:

```
Workflow({
  scriptPath: "${CLAUDE_PLUGIN_ROOT}/workflows/scan.js",
  args: { area: "$1", conventionPattern: "$2" }
})
```

This dispatches one finder per convention dimension, each returning
divergence candidates already filtered for the scope discipline above and
independently verified against the cited code. Tell the user the agent
count before launching. On return, render the result into
`analysis/$1/CONSISTENCY_SCAN.md` and `analysis/$1/consistency.json` per
**Write** below, then skip to **Present**.

## Method B — Direct subagent fan-out (fallback)

Spawn one **pattern-analyst** subagent per convention dimension, in
parallel. Prompt template:

"Survey `$1` for how **{dimension}** is handled across the codebase. Group
every distinct approach into a variant cluster with `file:line` examples.
For each cluster, check first whether it's already documented (CLAUDE.md,
house-rules.md, linter config, ADRs) — if so, report it as
`out-of-scope-documented` and do not detail it further. Check whether any
cluster is simply outdated for the version this codebase declares — if so,
report it as `out-of-scope-deprecated`. For everything else — two or more
valid, undocumented, currently-used variants — report each cluster: which
files/modules use it, an approximate count, and one representative
example."

Merge results, dedup overlapping clusters, and verify each cluster
yourself by reading a sample of the cited locations before writing.

## Write

Create `analysis/$1/consistency.json` — one entry per in-scope divergent
dimension:

```json
{
  "area": "$1",
  "dimensions": [
    {
      "id": "error-handling-style",
      "modules": ["billing/*", "shipping/*"],
      "variants": [
        { "label": "return Result<T,E>", "sites": 41, "example": "billing/charge.py:88-94" },
        { "label": "raise + catch at boundary", "sites": 17, "example": "shipping/dispatch.py:22-30" }
      ],
      "documented": false,
      "deprecatedForVersion": false
    }
  ],
  "outOfScope": [
    { "id": "docstring-format", "reason": "documented in CLAUDE.md §3" },
    { "id": "optional-typing", "reason": "deprecated for declared Python >=3.10 target — see self-assess idiom-auditor" }
  ]
}
```

This schema feeds `/consistency-map`'s matrix and `/consistency-canonize`'s
derivation directly — module × dimension cells, variant counts for
majority weighting.

Create `analysis/$1/CONSISTENCY_SCAN.md` in human-readable form:
- **Summary** (dimensions scanned, how many in-scope vs. routed elsewhere)
- **Divergence table** — one row per in-scope dimension: variant count,
  total sites, modules touched, rough split (e.g. "71% / 29%")
- **Out-of-scope appendix** — dimensions found but routed to documented-
  convention or version-modernization tooling, with the one-line reason

## Present

Report the count of in-scope divergent dimensions and total affected
sites. Suggest `/consistency-map $1` to see it visually, or
`/consistency-canonize $1` to go straight to derivation.
