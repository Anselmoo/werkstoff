---
name: self-assess-ci-topology
description: Audits this repository's git remotes, CI configuration, any publish/mirror scripts, and commit-signing consistency for redundant remotes, doc-vs-reality drift about CI, one-directional force-push mirrors with no reverse-sync path, and inconsistent commit signing (the green "Verified" vs grey "Unverified" badge — some commits signed, some not, or `commit.gpgsign` unset). Use this when the user asks to check our git remotes, audit CI setup, find redundant mirrors, verify the docs about CI/CD are accurate, or check commit signing / why some commits show grey/unverified / provenance (CI/git-topology claims only — for broader doc-vs-code drift on other topics, use self-assess-docs-drift).
---

Audit the current repository's **git/CI topology** — the remotes, the CI
config files, and any mirror/publish scripts — for redundancy and drift.
There is no analog to this in prior discovery tooling for legacy systems;
this only makes sense for a live repo with real remotes and CI history.

## Step 0 — Load settings, gather inputs

Read `.claude/self-assess.local.md` if it exists (see
`${CLAUDE_PLUGIN_ROOT}/references/settings.md`). If `enabled: false`, stop and say so. Note
`output_dir` (default `analysis/self-assess`) and `skip_verification`
(default `false`).

The workflow script has no filesystem access, so gather everything first:

```bash
git remote -v
```

Glob for CI config files: `.github/workflows/*`, `.gitlab-ci.yml`,
`.circleci/config.yml`, `azure-pipelines.yml`, `bitbucket-pipelines.yml`,
and any `scripts/*mirror*`/`scripts/*publish*`/`scripts/*sync*` files.
Glob for doc files the same way `self-assess-docs-drift` does
(`CLAUDE.md`, `README.md`, etc.) — you only need these to check CI-related
claims specifically, not full claim extraction.

Read `.claude/house-rules.md` (or the path named by `house_rules_path` in
the settings file) if it exists (pass `null` if absent). If the repo is
not under git (`git rev-parse --is-inside-work-tree` fails), stop here
and report that this skill has nothing to check.

Also gather the **commit-signing** evidence (the workflow can't run git
itself), so the scan can flag inconsistent provenance — the green
"Verified" vs grey "Unverified" badge a forge renders per commit:

```bash
git config --get commit.gpgsign            # empty = unset (new commits default unsigned)
git log --pretty=format:'%G?' | sort | uniq -c   # tally of signature statuses
```

`%G?` legend: `G` good/verified, `U` good unknown-validity, `X`/`Y` good but
expired sig/key, `R` good but revoked key, `B` bad, `E` signed but key not
available (shows grey), `N` unsigned. Pass the `commit.gpgsign` value as
`signingConfig` and the tally as `signatureDistribution` (both optional —
omit or pass `""` if not under git or history is empty).

## Step 1 — Run the scan

**Preferred — Workflow orchestration.** If the **Workflow tool** is
available in this session (this skill invocation is your authorization):

```
Workflow({
  scriptPath: "${CLAUDE_PLUGIN_ROOT}/workflows/ci-topology-scan.js",
  args: { repoPath: "<repo root, usually '.'>", remotesOutput: "<git remote -v output>", ciConfigFiles: [<found>], docFiles: [<found>], signingConfig: "<git config commit.gpgsign output>", signatureDistribution: "<%G? tally>", houseRules: <content or null>, skipVerification: <from settings, default false> }
})
```

It runs three finders (remotes/mirrors, CI-config-vs-docs drift,
commit-signing consistency) in parallel, dedups, then — unless
`skip_verification` is set — adversarially refutes every finding before it
reaches the report. With
`skip_verification`, deduped findings are reported directly and labeled
unverified. Any credential embedded in a remote URL is masked to a 2-4
character preview, cited by remote name rather than the raw URL — same
discipline as `security-auditor`. The finders/refuters are read-only by
design; **you** write the artifact below from the structured result.

**Fallback** (no Workflow tool) — spawn a **ci-topology-auditor** subagent:
"Audit this repo's `git remote -v` output for redundant remotes and
one-directional mirror risk (no reverse-sync path), cross-check CI config
files against any CI-related claims in the docs, and check commit-signing
consistency (`commit.gpgsign` unset while history is signed; a mix of signed
and unsigned commits from the `%G?` tally). Mask any credential in a remote
URL." Then verify each finding yourself by reading the cited evidence before
including it.

## Step 2 — Write the report

Create `<output_dir>/CI_TOPOLOGY.md`:
- **Summary** — remote count, CI config files found, findings by severity,
  refuted count (the false-positive rate the verification bought)
- **Findings table**, sorted by severity: category, title, evidence,
  description, recommended fix
- **Refuted candidates** — brief list
- If `injectionFlags` is non-empty, a prominent **"⚠ Instruction-shaped
  content found"** section

Also write `<output_dir>/ci_topology_summary.json` — a small machine-
readable sidecar `self-assess-portfolio` reads for its dashboard:
`{"remoteCount": N, "ciConfigFileCount": N, "findingsBySeverity": {...},
"findings": [...]}` (`findingsBySeverity` copied straight from the
workflow's `stats.bySeverity`).

`findings` is the workflow's own `findings` array (already computed —
do not re-derive it) — it already has the shared `{severity, title,
evidence, category}` shape every domain sidecar now uses, so copy it
through unchanged. Feeds `findings-dashboard.html`'s findings table and
`self-assess-transform-brief`.

## Present

Report: remote count, findings by severity, refuted count. If a High
finding exists (typically a mirror with no reverse-sync path, or a
doc claiming "no CI" contradicted by an actual workflow file), name it
first. Suggest: `glow -p <output_dir>/CI_TOPOLOGY.md`
