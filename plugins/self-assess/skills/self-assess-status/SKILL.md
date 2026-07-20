---
name: self-assess-status
description: Reports where self-assess's analysis stands for the current repository — which artifacts exist, whether they're stale relative to the current code, and the single most useful next skill to run. Use this when the user asks "where does self-assess stand", "what's stale in the self-assess analysis", "what should self-assess run next", or "self-assess status".
---

Report where self-assess's analysis of the current repository stands, in
one screen. This is a **read-only** skill — inspect, never modify.

This reports staleness of **this plugin's own artifacts** against current
repo state — it is not docs-vs-code drift itself (that's
`self-assess-docs-drift`'s job) — so the two skills' scopes never overlap:
status answers "has the code moved since we last checked," docs-drift
answers "does the doc's claim hold right now."

## 1 — Artifact inventory

Read `.claude/self-assess.local.md` if it exists (see
`${CLAUDE_PLUGIN_ROOT}/references/settings.md`) to get `output_dir` (default
`analysis/self-assess`) — other skills may be writing somewhere else if
this repo overrides it, and this skill must look in the same place they
do or every artifact reads as missing.

Check `<output_dir>/` and build a table — one row per skill, with
the artifact's presence and modification time:

| Skill | Artifacts |
|---|---|
| preflight | `PREFLIGHT.md` |
| stage-map | `STAGE_MAP.md`, `STAGE_MAP.html`, `stage_map.json` |
| docs-drift | `DOCS_DRIFT.md`, `docs_drift_summary.json` |
| ci-topology | `CI_TOPOLOGY.md`, `ci_topology_summary.json` |
| lint-audit | `LINT_AUDIT.md`, `lint_audit_summary.json` |
| extract-rules | `BUSINESS_RULES.md`, `DATA_OBJECTS.md`, `business_rules_summary.json` |
| complexity-score | `COMPLEXITY_SCORE.md`, `complexity_score_summary.json` |
| code-idiom | `CODE_IDIOM.md`, `code_idiom_summary.json` |
| arch-health | `ARCH_HEALTH.md`, `arch_health_summary.json` |
| transform-brief | `MODERNIZATION_BRIEF.md`, `TRANSFORM_SEQUENCE.mmd`, `TRANSFORM_MAPPING.mmd`, `transform_brief_summary.json` |

## 2 — Staleness

For each artifact that exists, compare its modification time against the
current repo state:

- If the repo is under git: run `git log -1 --format=%ct` for the whole
  repo (or, for finer signal, for the specific paths a skill actually
  reads — e.g. `stage_map.json` only cares about source files, not docs)
  and compare against the artifact's mtime. An artifact older than the
  latest relevant commit is **stale**.
- If not under git: compare the artifact's mtime against the newest mtime
  among the source files that skill reads.

Flag each stale artifact with which skill to re-run.

## 3 — Render the dashboard

Assemble a combined JSON object from whichever of the six
severity/category-bucketed domain sidecars actually exist under
`<output_dir>/` — `Read` each one that is present and `JSON.parse` it
(skip any that are missing; do not invent placeholder data for a skill
that has never run):

```json
{
  "docsDrift": <contents of docs_drift_summary.json, if present>,
  "ciTopology": <contents of ci_topology_summary.json, if present>,
  "lintAudit": <contents of lint_audit_summary.json, if present>,
  "businessRules": <contents of business_rules_summary.json, if present>,
  "codeIdiom": <contents of code_idiom_summary.json, if present>,
  "archHealth": <contents of arch_health_summary.json, if present>
}
```

This intentionally aggregates only these six domain skills.
`self-assess-stage-map` already has its own dedicated interactive viewer
(`STAGE_MAP.html`, rendered by that skill's own Step 3) and is not
duplicated here. `self-assess-portfolio` is a separate multi-repo
concern with a different shape of data (it compares across repositories,
not within severity buckets of one repo) and is also out of scope for
this single-repo dashboard. `self-assess-complexity-score` is excluded
for the same reason as `self-assess-stage-map`: it's a different shape of
data (a ranked complexity index, not severity/category buckets) — it
gets a row in the artifact-inventory table above, but no key in this
combined JSON and no entry in `findings-dashboard.html`'s `DOMAINS`
registry. `self-assess-transform-brief` is excluded for the same reason: a
transformation plan is not a pass/fail finding, so `decisionCounts` and
`openQuestions` don't fit a severity/category bucket either — it also gets
an inventory-table row only.

Each domain key is present only if its sidecar file exists — do not add
a key with an empty object as a stand-in for "not run yet"; the viewer
already renders a "not run yet" badge for a missing key. Use each
sidecar's fields exactly as written on disk; this skill does not
reshape or rename them.

Write this object as `<output_dir>/findings_dashboard_data.json` (a
plain `Write` call), then run the injection script — same
render-and-inject pattern `self-assess-stage-map` uses for its own
viewer (see that skill's "Step 3 — Render the interactive map" and
`scripts/render_stage_map.py`), and the same pattern the sibling
`confab` plugin's `confab-status` skill uses for its own dashboard:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/self-assess-status/scripts/render_dashboard.py" \
  "${CLAUDE_PLUGIN_ROOT}/assets/findings-dashboard.html" <output_dir>
```

`findings_dashboard_data.json` is derived from **untrusted source**
(category labels, rule names, and other values that ultimately trace
back to analyzed repo content) and gets injected into a `<script>`
block — the HTML parser closes `<script>` on the literal bytes
`</script>` regardless of JS string context, so a value containing
`x</script><script>...` would execute. The script handles the required
JSON-safe escaping (`<`, `>`, `&`); do not reimplement this inline.

If none of the six sidecars exist yet, still run the injection step —
the template's own "no data yet" empty state (in
`findings-dashboard.html`) handles an all-missing payload without
looking broken, so this skill never needs special-case logic for a
fresh install.

## 4 — Verdict

End with three lines:
- **Where you are** — which skills have been run at least once, and how
  recently.
- **What's stale** — or "nothing".
- **Next skill** — the single most useful next step: the first skill
  never run, or if all have run, the stalest one, with a one-line reason.

Then tell the user to view the dashboard: "view the dashboard at
`<output_dir>/findings-dashboard.html`" (open directly in a browser, no
build step — it's a self-contained file).
