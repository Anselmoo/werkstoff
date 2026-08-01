---
name: self-assess-preflight
description: This skill should be used when the user asks to "check if this repo is ready for self-assess", "run preflight", "can self-assess analyze this codebase", or before any other self-assess-* skill runs for the first time in a repo. Also invoked at the start of self-assess-autopilot's CHECK phase. Verifies language detection, tool availability, smoke-parseability, house-rules presence, git/CI presence, and doc presence, then assigns a Ready/Ready-with-gaps/Not-ready verdict per downstream skill.
---

# self-assess-preflight

Determine whether this repository is ready for self-assess's analysis skills, and which
downstream skills can run at full strength versus degraded.

## Step 0: Read settings and check the gate

Run, from the plugin root:

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/self_assess_cli.py check-enabled --repo <repo_root> --skill self-assess-preflight
```

A non-zero exit means the skill is disabled in `.claude/self-assess.local.md` -- stop and tell
the user plainly, quoting the stderr message. On success, the JSON on stdout carries the
resolved settings (including `output_dir`, default `analysis/self-assess`). Use that `output_dir` for
every output path in this skill, resolved through `resolve-output-path` (see Step 6) before
any write.

## Step 1: Run all 6 checks, unconditionally

Rule `preflight-runs-all-checks` requires every check below to run and report its own status,
even when an earlier check fails. Do not short-circuit. Wrap each check in isolation (a failed
`git` invocation, a missing manifest, a parse error) so one check's failure cannot prevent the
next from running:

1. **languages** -- glob the repo for manifest files (`package.json`, `pyproject.toml`,
   `go.mod`, `Cargo.toml`, `pom.xml`, etc.) and count files by extension. Call
   `detect-languages --manifests <json list of manifest basenames found> --extension-counts
   <json map of extension to count>`. This enforces the language-detection-threshold rule (an
   extension only counts once >=3 files exist and no manifest already claimed that language in
   pass 1) -- do not reimplement the threshold by hand.
2. **tools** -- probe for a language's usual toolchain (e.g. `python3 --version`, `node
   --version`, `go version`) for each detected language; record found/missing per tool.
3. **smoke_parse** -- for exactly one file per detected language (the smallest by line count is
   a reasonable pick), attempt a lightweight parse: Python via `python3 -m py_compile`,
   JavaScript/TypeScript via `node --check` (or a bare syntax check), Go via `gofmt -l`, etc. Do
   not smoke-parse more than one file per language -- that is this skill's own scope limit, not
   a downstream skill's job.
4. **house_rules** -- check for `.claude/house-rules.md`, falling back to `CLAUDE.md` with a
   `best-effort` label if absent.
5. **git_remotes_ci** -- check for a `.git` directory and at least one CI config file
   (`.github/workflows/*`, `.gitlab-ci.yml`, `Jenkinsfile`, `.circleci/config.yml`,
   `azure-pipelines.yml`).
6. **docs** -- check for `README.md`, `ARCHITECTURE.md`, `DECISIONS.md`, or ADR files.

Record each check's `name` (matching exactly: `languages`, `tools`, `smoke_parse`,
`house_rules`, `git_remotes_ci`, `docs`) and `status` (`pass`, `partial`, or `fail`) regardless
of outcome.

## Step 2: Assign per-skill verdicts

Using the check results, assign each downstream skill a verdict in
`{"Ready", "Ready-with-gaps", "Not-ready"}`:

- `self-assess-ci-topology` is `Not-ready` if `git_remotes_ci`'s git-presence sub-check fails
  (the skill's own rule refuses to run outside git).
- `self-assess-ui-audit` is `Ready-with-gaps` (never `Not-ready`) when no UI files are found --
  it degrades to "Not applicable" itself, this skill just flags the gap in advance.
- Any skill whose language was detected only via extension count (not manifest) is
  `Ready-with-gaps`.
- Everything else with a passing smoke-parse and detected language is `Ready`.

## Step 3: Validate before writing

Build `preflight_summary.json` with top-level `checks` (list of the 6 results above) and
`verdicts` (map of skill id to verdict), then validate it before writing:

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/self_assess_cli.py validate-artifact --kind preflight_summary --file <path-or-inline-json>
```

This rejects the artifact if any of the 6 required checks is missing or any verdict is outside
the three allowed values -- it is not enough to intend to run all 6 checks, the validator
confirms all 6 are actually present.

## Step 4: Write outputs

Resolve both output paths first:

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/self_assess_cli.py resolve-output-path --repo <repo_root> --filename PREFLIGHT.md
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/self_assess_cli.py resolve-output-path --repo <repo_root> --filename preflight_summary.json
```

A non-zero exit here means the configured `output_dir` or filename escapes the plugin's write
scope -- stop, do not write anywhere else instead. On success, write `PREFLIGHT.md` (a
human-readable table of the 6 checks and verdicts) and `preflight_summary.json` to the resolved
paths using the Write tool.

## Read-only constraint

This skill never uses Write/Edit for anything except the two output files above, and never runs
Bash with a mutating flag. All 6 checks are read-only inspection.
