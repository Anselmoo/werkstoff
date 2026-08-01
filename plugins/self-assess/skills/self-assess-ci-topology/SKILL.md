---
name: self-assess-ci-topology
description: This skill should be used when the user asks to "audit our git remotes", "check CI setup", "find redundant mirrors", "verify docs about CI/CD are accurate", or as part of self-assess-autopilot's CHECK phase. Audits git remote topology and CI configuration for redundancy, mirror risk, and doc-vs-config drift, masking every credential to a short preview.
---

# self-assess-ci-topology

Audit this repository's git remotes and CI/CD configuration.

## Step 0: Settings gate, then the git-repo gate

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/self_assess_cli.py check-enabled --repo <repo_root> --skill self-assess-ci-topology
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/self_assess_cli.py require-git-repo --repo <repo_root> --caller self-assess-ci-topology
```

The second call enforces "MUST NOT run if repo is not under git" -- a non-zero exit here means
stop entirely and tell the user this skill only applies to git repositories.

## Step 1: Gather raw topology

Run `git remote -v` and glob CI config files (`.github/workflows/*.yml`, `.gitlab-ci.yml`,
`Jenkinsfile`, `.circleci/config.yml`, `azure-pipelines.yml`). Also glob docs mentioning CI
(`README.md`, `CONTRIBUTING.md`, `docs/ci*.md`).

If the `compass:compass-solve`-style Workflow tool is available, prefer dispatching
`self-assess:self-assess-ci-topology`'s own bundled workflow (class-scoped parallel finders for
remotes/mirrors, CI-config-vs-docs drift, and commit-signing) with
`{repoPath, remotesOutput, ciConfigFiles, docFiles, skipVerification}`. Otherwise dispatch the
`ci-topology-auditor` agent directly with the same inputs.

## Step 2: Mask every credential before it leaves this step

Rule `credential-masking-in-output` applies to every remote URL and any embedded token before
it appears in a finding, a printed message, or a written file:

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/self_assess_cli.py mask-text --text "<raw git remote -v output>"
```

Never pass the raw `git remote -v` output (or any raw credential substring) into a finding,
CI_TOPOLOGY.md, or ci_topology_summary.json -- always mask first. The masking function reduces
any userinfo/token to a 2-4 character preview plus `***`; there is no code path that returns
the original secret.

## Step 3: Verify findings

Unless `skip_verification` is set, confirm each finding by reading the actual remote config and
CI files cited -- never assert redundancy or drift from a doc claim alone.

## Step 4: Validate and write

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/self_assess_cli.py validate-artifact --kind ci_topology_summary --file <path-or-inline-json>
```

The validator rejects the artifact outright if any finding still carries a `raw_remote_url`
field -- masking must happen before this call, not be deferred to it.

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/self_assess_cli.py resolve-output-path --repo <repo_root> --filename CI_TOPOLOGY.md
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/self_assess_cli.py resolve-output-path --repo <repo_root> --filename ci_topology_summary.json
```

Write `CI_TOPOLOGY.md` and `ci_topology_summary.json` to the resolved paths, using only masked
remote references throughout.

## Read-only constraint

Never alter remotes (`git remote add/remove/set-url`) or CI config files. This skill only
reads and reports.
