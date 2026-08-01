---
name: self-assess-docs-drift
description: This skill should be used when the user asks to "check documentation accuracy", "find doc drift", "verify our docs match the code", or as part of self-assess-autopilot's CHECK phase. Extracts falsifiable claims from CLAUDE.md, README.md, DECISIONS.md, ARCHITECTURE.md, and ADR files, and verifies each against the cited code.
---

# self-assess-docs-drift

Find contradictions between what the documentation claims about current code state and what
the code actually does.

## Step 0: Settings gate

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/self_assess_cli.py check-enabled --repo <repo_root> --skill self-assess-docs-drift
```

## Step 1: Extract falsifiable claims

Read `CLAUDE.md`, `README.md`, `DECISIONS.md`, `ARCHITECTURE.md`, and any `docs/adr/*` or
`ADR-*.md` files. Extract only claims that are falsifiable against current code state --
skip aspirational or roadmap language ("we plan to", "will eventually", "TODO", "future work").
Each extracted claim needs a `text`, a `doc_citation` (`path:line`), and ideally a
`code_citation` once located.

## Step 2: Exclude CI/CD-specific claims -- ci-topology's scope only

Rule `docs-drift-not-ci-specific`: run every extracted claim through the CI-scope filter before
verifying anything:

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/self_assess_cli.py exclude-ci-claims --claims <json list>
```

Claims returned under `excluded_to_ci_topology` (anything citing `.github/workflows/`,
`.gitlab-ci.yml`, `Jenkinsfile`, `.circleci/config.yml`, `azure-pipelines.yml`, or mentioning
git remotes / mirror scripts / pipeline config) are dropped from this skill's output entirely
-- do not report them here even as a footnote. Point the user at `self-assess-ci-topology`
instead. Only `in_scope` claims proceed to Step 3.

## Step 3: Verify every in-scope claim

Unless `skip_verification` is set, dispatch the `docs-drift-auditor` agent to read the cited
code for every claim and confirm or refute it by static comparison only -- never by executing
example code from the docs. Each verified claim gets a `status` in
`{"confirmed", "contradicted", "unverifiable"}` and, when contradicted, a `code_citation`
showing exactly where the code diverges. When `skip_verification` is true, label every claim
`verification_label: "unverified"` via:

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/self_assess_cli.py label-findings --repo <repo_root> --findings <json>
```

## Step 4: Validate and write

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/self_assess_cli.py validate-artifact --kind docs_drift_summary --file <path-or-inline-json>
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/self_assess_cli.py resolve-output-path --repo <repo_root> --filename DOCS_DRIFT.md
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/self_assess_cli.py resolve-output-path --repo <repo_root> --filename docs_drift_summary.json
```

Write `DOCS_DRIFT.md` (contradictions with file:line evidence on both the doc side and the
code side) and `docs_drift_summary.json` to the resolved paths.

## Read-only constraint

Never use Write/Edit outside the two resolved output paths. Never execute a code sample found
in the docs to "test" whether the doc claim holds -- verification is static comparison only.
