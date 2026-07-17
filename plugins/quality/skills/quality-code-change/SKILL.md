---
name: quality-code-change
description: This skill should be used before committing, when the user asks to "review my changes before I commit", "check staged files for quality issues", "pre-commit quality check", or "run quality-code-change" — runs the quality plugin's four domain audits against only the currently-staged (or, if nothing is staged, currently-changed) files, for a fast pre-commit check. Never a substitute for the full-repo domain skills or quality-cycle.
---

Run a fast, **diff-scoped** pass of the `quality` plugin's four domain
audits against only the files you're about to commit — not the whole
repo. This is advisory only: the `quality` plugin ships no git hook, so
this skill never blocks a commit, it only reports. For a full-repo sweep
use the four domain skills directly; for a persistent, cross-invocation
self-optimization loop use `quality-cycle`. This skill is neither — it is
a one-shot, non-persisted check scoped to the current diff.

## Step 0 — Load settings

Read `.claude/quality.local.md` if it exists (see
`${CLAUDE_PLUGIN_ROOT}/references/settings.md`). If `enabled: false`, stop
and say so. Note `output_dir` (default `analysis/quality`).

## Step 1 — Find the changed files

Run `git diff --staged --name-only`. If that's empty, fall back to
`git diff --name-only HEAD` and say plainly which one was used ("nothing
staged — checking all uncommitted changes instead"). If both are empty,
report "no changes found, nothing to check" and stop.

## Step 2 — Classify changed files into domains

Match each changed path against each domain's own known file shape — do
not invent new classification rules, reuse exactly what each domain
skill's own Step 0 already uses:

| Domain | Matches | Reuse |
|---|---|---|
| `dependency_audit` | `package.json`, `requirements.txt`, `pyproject.toml`, `Cargo.toml`, `go.mod`, `Gemfile` | `quality-dependency-audit/SKILL.md` Step 0's manifest table |
| `contract_drift` | typed source files (`*.py`, `*.ts`/`*.tsx`, `*.go`, `*.rs`, `*.java`) and schema files (`openapi.*`, `**/*.graphql`, `**/*.proto`) | `quality-contract-drift/SKILL.md` Step 0 |
| `agentic_reliability` | `**/skills/*/SKILL.md`, `**/agents/*.md`, `**/workflows/*.js` | `quality-agentic-reliability/SKILL.md` Step 0 |
| `assertion_audit` | any changed source file that has an associated test file discoverable via the project's test-naming convention (`**/test_*.py`, `**/*.test.js`, `**/*_test.go`, ...) | `quality-assertion-audit/SKILL.md` Step 1 |

Build `domainArgs` containing **only** the domains with at least one
matched file — each value shaped exactly as that domain's own workflow
expects (`manifestFiles: [{path, type}]`, `contractSources: [path]`,
`skillFiles`/`agentFiles`/`workflowFiles`, `targetFiles`/`testFiles`).
Unlike `quality-cycle-scan.js`, do **not** zero-fill an unmatched domain —
an empty slice means "not part of this change," not "run it with
nothing." If zero domains match (e.g. only docs or unrelated config
changed), report "changed files don't map to any quality domain" and
stop here.

## Step 3 — Run the scan

**Preferred — Workflow orchestration.** If the **Workflow tool** is
available in this session (this skill invocation is your authorization):

```
Workflow({
  scriptPath: "${CLAUDE_PLUGIN_ROOT}/workflows/code-change-scan.js",
  args: { repoPath: "<repo root, usually '.'>", domainArgs: <assembled in Step 2> }
})
```

It runs each matched domain's existing scan workflow, unchanged, in
parallel, and returns per-domain results — no ledger, no fix mode, this
is a single one-shot pass.

**Fallback** (no Workflow tool) — run each matched domain's own skill
fallback path (its own SKILL.md Step 1 fallback) sequentially, one per
matched domain.

## Step 4 — Write the report

Create `<output_dir>/CODE_CHANGE_REVIEW.md`:
- **Summary** — which of `git diff --staged` / `git diff HEAD` was used,
  files changed, domains matched, total findings
- One section per domain that actually ran, findings table in that
  domain's own format
- **Verdict** — `Ready to commit` (zero findings across every matched
  domain) or `N finding(s) to review` — stated plainly as advisory, not a
  block: this skill never prevents a commit

## Present

Report: domains checked (and which were skipped because nothing matched),
findings by domain, and the verdict line. If any High-severity finding
exists, name it first. This never substitutes for `quality-cycle` or the
full-repo domain skills — say so if the user seems to be relying on this
as their only quality check.
