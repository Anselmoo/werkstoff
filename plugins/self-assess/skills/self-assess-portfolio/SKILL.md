---
name: self-assess-portfolio
description: This skill should be used when the user asks to "sweep multiple repos", "assess our whole portfolio", "grade all our projects", or names a parent directory containing several git repositories. Grades each repo Red/Amber/Green/Gray by worst-signal-wins, and requires an explicit portfolio directory when cwd is itself a git repo.
---

# self-assess-portfolio

Sweep a directory of repositories and grade each one's self-assess health.

## Step 1: Scope gate -- refuse to infer cwd's parent as the portfolio

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/self_assess_cli.py portfolio-scope-gate --cwd <cwd> --explicit-dir <user-named directory, if any>
```

Rule `portfolio-cwd-git-repo-check`: if `cwd` is itself a git repository and the user did not
name an explicit portfolio directory, this refuses. Ask the user to name the portfolio
directory explicitly rather than walking up to `cwd`'s parent -- a git repo's parent is not an
implicit portfolio container.

## Step 2: Enumerate repos

List immediate subdirectories of the (now-confirmed) portfolio directory that contain a `.git`
directory.

## Step 3: Grade each repo, worst-signal-wins

For each repo, check whether `<repo>/analysis/self-assess/` (or its configured `output_dir`) has any
artifacts. Then:

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/self_assess_cli.py grade-repo --has-artifacts --has-high --has-medium-or-gaps
```

(Pass `--has-artifacts` only if artifacts exist; pass `--has-high` only if any summary contains
a High-severity finding; pass `--has-medium-or-gaps` only if any summary contains a
Medium/Low finding or a `Ready-with-gaps` verdict.) Rule
`portfolio-grade-worst-signal-wins`: a repo with **no artifacts** always grades `Gray` --
this branch is checked first in the grading function and cannot be overridden by any
finding, so a never-assessed repo can never read as falsely healthy (`Green`). Never
synthesize a placeholder grade for an unassessed repo beyond `Gray`.

## Step 4: Write the portfolio report

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/self_assess_cli.py resolve-output-path --repo <portfolio_dir> --filename self-assess-portfolio.html
```

Note the output lands in the **portfolio directory**, not any single repo's `output_dir` --
this is the one skill whose output is not scoped to a single repo's `analysis/self-assess/`. Write
`self-assess-portfolio.html` with one row per repo: grade, and (for graded repos) a short
summary of what drove the grade; for `Gray` repos, "not yet assessed" and nothing more.

## Read-only constraint

Never use Write/Edit outside the resolved portfolio report path, and never modify anything
inside a swept repo.
