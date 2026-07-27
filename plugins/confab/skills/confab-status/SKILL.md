---
name: confab-status
description: "Use when the user asks where confab's quality analysis stands, which reports are stale, what to run next, or wants a dashboard of all findings so far. Read-only: never triggers an audit itself, only reports on what has already run."
---

Report the current state of confab's analysis for this repository: which
domain audits have run, whether their results are stale relative to the
latest commit, and the single most useful next action.

## Steps

1. Determine `repo_root`.
2. Run:
   ```
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/status_dashboard.py" <repo_root>
   ```
   This is read-only — it opens existing `analysis/confab/*_summary.json`
   sidecars and `analysis/confab/ledger.json` if present, and runs `git log -1`
   (read-only) to establish a staleness reference. It never runs an audit
   itself. It writes `analysis/confab/findings_dashboard_data.json` and
   `analysis/confab/reports/findings-dashboard.html`, and prints the same data
   plus a `suggestion` field to stdout.
3. Report to the user, per domain: has it ever run, how many findings,
   and whether it's stale relative to the latest commit. Report whether a
   `confab-cycle` ledger exists and, if so, whether its last pass
   converged.
4. Surface the `suggestion` field as your one recommended next action —
   it's already picked using this priority: a domain that has never run,
   else the stalest domain that has run, else `confab-cycle` if a ledger
   exists but hasn't converged, else `confab-cycle` if no ledger exists
   yet at all, else "nothing pending." Do not second-guess this ordering
   with your own priority call — if you disagree with what it suggests
   for this specific repository, say so as a caveat, but still report
   the suggestion itself accurately.
5. Mention the HTML dashboard path so the user can open it if they want a
   visual view.

## What NOT to do

- Do not run any of the four domain-audit skills or `confab-cycle` from
  within this skill — `confab-status` only reads what already exists.
- Do not fabricate a "last run" time for a domain that has never
  produced a summary sidecar — report it as "never run," not "unknown"
  or a guessed date.
