---
name: confab-status
description: This skill should be used when the user asks "where does quality stand", "what's stale in the quality analysis", "what should I run next", "quality status", or "confab-status" for the current repository. Reports which of the confab plugin's own artifacts exist, whether each is stale relative to current repo state, and the single most useful next skill to run.
---

Report where the `confab` plugin's analysis of the current repository
stands, in one screen. This is a **read-only** skill — inspect, never
modify.

This reports staleness of **this plugin's own artifacts** against current
repo state — it does not audit dependencies, assertions, contracts, or
agentic reliability itself (that is each domain skill's job), and it does
not run or drive `confab-cycle` itself, only surfaces its last-written
ledger state — so `confab-status`'s scope never overlaps with the six
skills it reports on. This also does not report on `self-assess`'s
artifacts (a sibling plugin in this same repo, with its own
`self-assess-status` skill for that) — the two plugins' status skills
never overlap.

## 1 — Artifact inventory

Read `.claude/confab.local.md` if it exists (see
`${CLAUDE_PLUGIN_ROOT}/references/settings.md`) to get `output_dir`
(default `analysis/confab`) — other skills may be writing somewhere else
if this repo overrides it, and this skill must look in the same place
they do or every artifact reads as missing.

Check `<output_dir>/` and build a table — one row per skill, with the
artifact's presence and modification time:

| Skill | Artifacts |
|---|---|
| confab-preflight | `PREFLIGHT.md` |
| confab-dependency-audit | `DEPENDENCY_AUDIT.md`, `dependency_audit_summary.json` |
| confab-assertion-audit | `ASSERTION_AUDIT.md` |
| confab-contract-drift | `CONTRACT_DRIFT.md` |
| confab-agentic-reliability | `AGENTIC_RELIABILITY.md` |
| confab-code-change | `CODE_CHANGE_REVIEW.md` |
| confab-cycle | `CONFAB_CYCLE.md`, `ledger.json` |

## 2 — Staleness

For each artifact that exists, compare its modification time against the
current repo state:

- If the repo is under git: run `git log -1 --format=%ct` for the whole
  repo (or, for finer signal, for the specific paths a skill actually
  reads — e.g. `confab-dependency-audit` only cares about manifest files,
  not source code) and compare against the artifact's mtime. An artifact
  older than the latest relevant commit is **stale**.
- If not under git: compare the artifact's mtime against the newest mtime
  among the source files that skill reads.

Flag each stale artifact with which skill to re-run.

## 3 — Render the dashboard

Assemble a combined JSON object from whichever of the four domain
sidecars actually exist under `<output_dir>/` — `Read` each one that is
present and `JSON.parse` it (skip any that are missing; do not invent
placeholder data for a skill that has never run):

```json
{
  "dependencyAudit": <contents of dependency_audit_summary.json, if present>,
  "assertionAudit": <contents of assertion_audit_summary.json, if present>,
  "contractDrift": <contents of contract_drift_summary.json, if present>,
  "agenticReliability": <contents of agentic_reliability_summary.json, if present>
}
```

Each domain key is present only if its sidecar file exists — do not add
a key with an empty object as a stand-in for "not run yet"; the viewer
already renders a "not run yet" badge for a missing key. Use each
sidecar's fields exactly as written on disk; this skill does not
reshape or rename them.

Also `Read` `<output_dir>/ledger.json` if present (written by
`confab-cycle`) and add it as a `cycle` key: `{"cycle": <ledger.cycle>,
"pass": <ledger.pass>, "mode": <ledger.mode>, "constraint":
<ledger.constraint>, "domains": <ledger.domains>}`. Omit the `cycle` key
entirely if no ledger exists yet — same "don't invent a not-run-yet
placeholder" rule the four domain keys already follow. This skill still
never runs `confab-cycle` itself; it only surfaces its last-written
state, same as every other domain key here.

Write this object as `<output_dir>/findings_dashboard_data.json` (a
plain `Write` call), then run the injection script — same
render-and-inject pattern `self-assess-stage-map` uses for its own
viewer (see that skill's "Step 3 — Render the interactive map" and
`scripts/render_stage_map.py`):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/confab-status/scripts/render_dashboard.py" \
  "${CLAUDE_PLUGIN_ROOT}/assets/findings-dashboard.html" <output_dir>
```

`findings_dashboard_data.json` is derived from **untrusted source**
(package names, contract types, category labels, and other values that
ultimately trace back to analyzed repo content) and gets injected into a
`<script>` block — the HTML parser closes `<script>` on the literal
bytes `</script>` regardless of JS string context, so a value containing
`x</script><script>...` would execute. The script handles the required
JSON-safe escaping (`<`, `>`, `&`); do not reimplement this inline.

If none of the four sidecars exist yet, still run the injection step —
the template's own "no data yet" empty state (in
`findings-dashboard.html`) handles an all-missing payload without
looking broken, so this skill never needs special-case logic for a
fresh install.

## 4 — Verdict

End with three lines:
- **Where you are** — which skills have been run at least once, and how
  recently.
- **What's stale** — or "nothing".
- **Next skill** — the single most useful next step, chosen from
  `confab-preflight`, `confab-dependency-audit`,
  `confab-assertion-audit`, `confab-contract-drift`, or
  `confab-agentic-reliability`: the first skill never run, or if all
  have run, the stalest one, with a one-line reason. If all four have run
  at least once and `ledger.json` exists but its last-recorded pass did
  not converge, suggest `confab-cycle` instead, naming its recorded
  `constraint` domain as the reason.

Then tell the user to view the dashboard: "view the dashboard at
`<output_dir>/findings-dashboard.html`" (open directly in a browser, no
build step — it's a self-contained file).
