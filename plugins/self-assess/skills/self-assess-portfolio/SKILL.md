---
name: self-assess-portfolio
description: Sweeps every repo under a parent directory and renders a heat-map dashboard from each repo's existing self-assess artifacts — languages, stage/wire counts, docs-drift contradictions, CI findings, lint violations, and an honest "not yet assessed" marker for repos with no artifacts yet. Use this when the user asks to sweep all our repos, get a portfolio view across our services, health-check our repos, which repo needs attention, or run self-assess across the whole org/monorepo-of-repos.
---

Build a **portfolio heat-map** across every repo under a parent
directory, from each repo's existing self-assess artifacts. This is
read-only aggregation, not re-analysis — a repo self-assess has never
run against shows up honestly as **not yet assessed**, never fabricated.

This mirrors `code-modernization`'s `modernize-assess --portfolio`
pattern, adapted from "how big and risky is this legacy system" to "how
healthy is this live repo, per self-assess's own findings."

## Step 0 — Determine the parent directory

First, determine whether the **current working directory is itself a git
repo** — this decides whether portfolio mode even applies here:

```bash
[ -d ".git" ] && echo "cwd-is-a-repo" || echo "cwd-is-not-a-repo"
```

- **If cwd has its own `.git`** (`cwd-is-a-repo`): this is a single
  project, not a portfolio container, regardless of what its parent
  directory happens to contain. Do **not** infer or walk up to cwd's
  parent under any circumstance — a project's parent directory is not
  implicitly a "portfolio" just because it exists.
  - If the user's request named no directory (e.g. just "run
    self-assess-portfolio" / "sweep our repos"), tell them portfolio mode
    doesn't apply to a single repo and point them at `self-assess-status`
    or `self-assess-preflight` instead for a single-repo view. **Stop
    here — do not run Step 1.**
  - If the user's original request clearly implies they want a
    multi-repo sweep even though cwd is itself a repo (e.g. they named an
    organization, a workspace of several projects, or explicitly said
    "across all our repos"), ask them to name the actual parent/container
    directory explicitly — never infer it from cwd's path. **Stop here
    until they answer.**
- **If cwd is not itself a git repo** (`cwd-is-not-a-repo`): cwd is a
  plausible portfolio container. Use cwd as `<parentDir>` if the user
  didn't name one, or use the directory the user named if they did.
- **If the user explicitly named a directory** (regardless of what cwd
  is), use exactly that directory as `<parentDir>` — an explicit name
  always wins over any inference. Still worth a one-line sanity check: if
  the named directory itself has a `.git`, tell the user it looks like a
  single repo, not a container, and confirm before proceeding rather than
  silently sweeping its parent or its subdirectories.

Only ever treat a directory as a valid portfolio scope if it is **not
itself a git repo** but its immediate subdirectories are (this is what
Step 1 enumerates next) — never guess a directory that might sweep
unrelated repos.

## Step 1 — Enumerate repos

This assumes Step 0 already confirmed `<parentDir>` is not itself a git
repo — don't run this step if Step 0 stopped early.

```bash
for d in "<parentDir>"/*/; do
  [ -d "${d}.git" ] && echo "${d%/}"
done
```

Every immediate subdirectory that is itself a git repo. Skip anything
that isn't (a `node_modules/`, a stray non-repo directory) — do not error
on them, just don't include them.

## Step 2 — Read each repo's existing artifacts

For each repo, first check whether it has its own
`.claude/self-assess.local.md` with an `output_dir` override (read it if
present, default `analysis/self-assess` otherwise — same settings file
`self-assess-status` reads, just once per repo here instead of once for
the current repo). Then `Read` whichever of these exist, skipping any
that don't:

- `<output_dir>/preflight_summary.json`
- `<output_dir>/stage_map_summary.json`
- `<output_dir>/docs_drift_summary.json`
- `<output_dir>/ci_topology_summary.json`
- `<output_dir>/lint_audit_summary.json`
- `<output_dir>/business_rules_summary.json`
- `<output_dir>/complexity_score_summary.json`

A repo with **none** of these present is **not yet assessed** — record
that plainly, do not run any skill against it yourself (that's what
`self-assess-preflight`/etc. are for, on request) and do not synthesize
placeholder numbers for it.

## Step 3 — Grade each assessed repo

For each repo that has at least one summary, compute a simple health
color, worst-signal-wins:

- **Red** — `preflight_summary.json`'s any verdict is `"Not-ready"`, or
  `ci_topology_summary.json`/`lint_audit_summary.json`'s
  `*BySeverity.High` is non-zero.
- **Amber** — any confirmed contradiction, finding, or violation exists
  at all (even Medium/Low), or any preflight verdict is
  `"Ready-with-gaps"`, or `business_rules_summary.json`'s `needsSme` is
  non-zero (a P0 rule still needs SME confirmation).
- **Green** — every available summary is clean (zero contradictions,
  zero findings, zero violations, all verdicts `"Ready"`).
- **Gray** — not yet assessed (Step 2).

Don't grade on data you don't have — a repo whose `docs_drift_summary.json`
is missing simply doesn't factor docs-drift into its grade; note which
summaries were available per repo so the grade's basis is legible, not a
black box.

## Step 4 — Render the dashboard

Write `<parentDir>/self-assess-portfolio.html` (this spans multiple
repos, so it lives at the parent level, not inside any one repo's
`analysis/self-assess/`) — dark `#1e1e1e` bg, `#d4d4d4` text, `#cc785c`
accent, system-ui font, all CSS inline, matching `code-modernization`'s
topology/portfolio styling convention. One row per repo; columns:
**Repo · Languages · Stages/Wires · Docs Contradictions · CI Findings ·
Lint Violations · Complexity Index · Health**. Color-grade the Health cell
(green→amber→red, gray for not-yet-assessed). The **Complexity Index**
column is sourced from `complexity_score_summary.json`'s
`topComplexityStage`/`complexityByStage` if present, blank/dash if the
sidecar is absent — it is purely informational and never a factor in the
Health cell's grade (Step 3 above); a high-complexity repo can still be
Green if nothing else is wrong with it. Below the table, 2-3 sentences:
which repo to prioritize first and why (worst health grade, or the repo
with the most confirmed findings) — and, separately, which repos are
still unassessed and worth a `self-assess-preflight` run.

## Present

Tell the user the dashboard is ready at `<parentDir>/self-assess-portfolio.html`.
Print a compact summary table in the session too — for portfolios larger
than ~30 repos, cap the in-session table to the worst 10 by health grade
plus a count of the rest, and say so explicitly (the full list is always
in the HTML; never silently truncate without saying you did).
