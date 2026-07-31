---
name: self-assess-status
description: This skill should be used when the user asks "where does self-assess stand", "what's stale in our analysis", "what should we run next", or "self-assess status". Reports which artifacts exist, whether they're stale relative to the latest commit, and never fabricates data for a skill that has not run.
version: 0.1.0
---

# self-assess-status

Report the current state of self-assess's analysis for this repository, without inventing
anything for a skill that has never run.

## Step 0: Settings gate

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/self_assess_cli.py check-enabled --repo <repo_root> --skill self-assess-status
```

## Step 1: Find only artifacts that actually exist

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/self_assess_cli.py status-present-artifacts --repo <repo_root>
```

The `present` map contains a key ONLY for a finding-producing skill whose sidecar JSON file
exists on disk right now. Rule `status-no-fabrication`: never add a key with an empty object,
a placeholder, or a guessed status for a skill that has not run -- if it is not in `present`,
omit it from the dashboard entirely.

The same call also returns a `structural` map, built the identical way, for
`self-assess-complexity-score`, `self-assess-stage-map`, and `self-assess-transform-brief` --
these are progress/synthesis artifacts, not findings domains, so `structural`'s contents MUST
NEVER be folded into `present` or counted by `recommend_transform_brief` (running
self-assess-stage-map is not itself a finding). But they ARE part of the dashboard: a user
asking "where does self-assess stand" needs to know stage-map has already run, not just that no
findings-producing skill has. Surface `structural` as its own section, distinct from `present`'s
findings table, applying the same `status-no-fabrication` rule (omit a skill entirely if it is
not in `structural`, never fabricate a placeholder for one that hasn't run).

## Step 2: Staleness

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/self_assess_cli.py staleness-check --repo <repo_root> --artifact <path1> --artifact <path2> ...
```

Pass every path from **both** `present` and `structural`. `stale: true` means that artifact's
mtime predates the repo's latest commit -- surface this per-artifact in the dashboard, in
whichever section (findings or structural) that artifact belongs to. If the repo has no commits
or is not under git, `latest_commit_ts` is `null` and every staleness value is `null` (unknown) --
report it as "staleness unknown," never guess `stale: false`.

## Step 3: Recommend transform-brief when warranted

The same `status-present-artifacts` call returns `recommend_transform_brief: true` when at
least one reporting sidecar exists but `MODERNIZATION_BRIEF.md` does not. Surface this
recommendation prominently when true.

## Step 4: Write outputs

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/self_assess_cli.py resolve-output-path --repo <repo_root> --filename findings-dashboard.html
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/self_assess_cli.py resolve-output-path --repo <repo_root> --filename findings_dashboard_data.json
```

Write `findings-dashboard.html` (a static HTML summary) and `findings_dashboard_data.json`
(only the keys actually present, plus staleness and the transform-brief recommendation).

## Read-only constraint

Never use Write/Edit outside the two resolved output paths.
