---
name: self-assess-preflight
description: Checks whether the current repository is ready for self-assess's analysis skills to run well. Detects the language stack, verifies analysis tooling is present, smoke-parses a real file per detected language, checks for a house-rules.md, and checks git-remote/CI-config readability. Use this when the user asks to run self-assess, check whether self-assess can run here, or before running self-assess-stage-map, self-assess-docs-drift, self-assess-ci-topology, or self-assess-lint-audit for the first time in a repo.
---

Check whether the current repository (the working directory, or a path the
user names) is ready for self-assess's analysis skills, and report exactly
what to fix before they run into it. Run every check even when an earlier
one fails — the goal is one complete readiness report, not the first error.

This operates on the repo root in place — there is no `legacy/$1`-style
argument. If the user names a specific path, use that as the repo root
instead of the working directory.

## Check 0 — Load settings

Read `.claude/self-assess.local.md` if it exists at the repo root (`Read`
tool; not an error if absent — every setting below has a default). See
`${CLAUDE_PLUGIN_ROOT}/examples/self-assess.local.md` for the template and
`${CLAUDE_PLUGIN_ROOT}/references/settings.md` for the full field list. If `enabled: false`,
stop here and tell the user self-assess is disabled for this repo (per
the settings file) rather than running any check. Otherwise note which
non-default overrides are active (`house_rules_path`, `output_dir`,
`languages`, `skip_verification`, `lint_max_rules`) so the report can
list them — every other skill re-reads this same file independently, so
getting this right once here doesn't exempt them from checking it too.

## Check 1 — Detect the stack

If `languages` is set (non-empty) in the settings file, skip detection
entirely and use that list verbatim — it's an explicit override, not a
hint, and takes precedence over anything below.

Read `${CLAUDE_PLUGIN_ROOT}/references/language-support.md` — it is the
**canonical, single source of truth** for detection (`self-assess-stage-map`
Step 0 reads the same file rather than maintaining a second list; do not
hand-roll your own manifest list here). Run its two-pass algorithm:

1. **Manifest-based.** Glob for the manifest pattern(s) in the reference's
   table (20 common languages covered explicitly; any other recognizable
   ecosystem manifest counts too — the table is illustrative, not
   exhaustive).
2. **Extension-frequency fallback, for manifest-less stacks.** Glob by file
   extension and count files per extension. Any extension with at least 3
   files and no owning manifest already detected in pass 1 is still a
   detected language (this is what makes Shell — and anything else with no
   conventional manifest — actually detectable; do not skip this pass).

Report the rough file split per language found in either pass. This
drives which of Checks 2–3 apply and which per-language finders
`self-assess-stage-map` will need to run — a language only reaches
`self-assess-stage-map`'s per-language finder dispatch if it's detected
here, so an incomplete Check 1 silently starves that skill regardless of
how general its own per-language fallback is.

## Check 2 — Analysis tooling

For each detected language, check availability (`command -v`) of the
tools its stage-map extractor and lint-audit checks lean on, and report
what degrades without them:

| Language | Tool | Used by | Without it |
|---|---|---|---|
| Python | `python3` (with `ast` — stdlib, always present) | stage-map | none — always available |
| Python | `ruff` | lint-audit | convention checks fall back to grep-based pattern matching, coarser |
| Rust | `cargo` | stage-map, lint-audit | dependency graph falls back to hand-parsing `Cargo.toml`; no `cargo metadata` cross-check |
| TS/JS | `node` | stage-map | import extraction falls back to a regex pass instead of a real parse |
| any | `git` | ci-topology, self-assess-status | remote/staleness checks skipped, reported as a gap |

Include the platform's install one-liner for anything missing.

## Check 3 — Smoke-parse (prove it works on this codebase, not just presence)

For each detected language, pick one representative source file and prove
the stage-map extractor can actually parse it:

- **Python** — `python3 -c "import ast, sys; ast.parse(open(sys.argv[1]).read())" <file>`
- **Rust** — a `use`/`mod` grep pass plus confirming `Cargo.toml` parses as
  valid TOML for the crate the file belongs to
- **TS/JS** — confirm `node --check <file>` succeeds, or that the file's
  `import`/`require` statements match the expected syntax if no runtime is
  available

A failed smoke-parse is the most valuable output of this check — report
the actual error (syntax the extractor doesn't handle, an unusual module
layout) rather than letting it surface later, less legibly, inside
`self-assess-stage-map`.

## Check 4 — House rules

Check for `.claude/house-rules.md` at the repo root, or the path named by
`house_rules_path` in the settings file if that override is set. If present, report
its size and confirm it's non-empty prose (not a placeholder). If absent,
say so plainly: `self-assess-lint-audit` will degrade to best-effort
checks against `CLAUDE.md` alone, clearly labeled, and full convention
enforcement is unavailable until the repo owner writes one.

## Check 5 — Git remotes and CI config

If the repo is under git, run `git remote -v` and report what's found —
this is what `self-assess-ci-topology` needs to be useful, not just
present. Check for CI config files (`.github/workflows/*`,
`.gitlab-ci.yml`, `.circleci/config.yml`, etc.) and note how many were
found. If the repo is not under git, say so — `self-assess-ci-topology`
has nothing to do.

## Check 6 — Docs present

Check for `CLAUDE.md`, `README.md`, and any ADR-shaped files (`DECISIONS.md`,
`docs/adr/*`, `ADR-*.md`) — what `self-assess-docs-drift` will mine claims
from. Report what's found; if nothing is found, say so — docs-drift will
have nothing to check.

## Report

Write `<output_dir>/PREFLIGHT.md` (`output_dir` defaults to
`analysis/self-assess`, overridable in the settings file): a status table
(one row per check, ✅/⚠️/❌, what was found, the fix for anything not
green), a line listing any active settings overrides from Check 0,
followed by a **Ready / Ready-with-gaps / Not-ready** verdict per
downstream skill:

- **`stage-map`** — needs Check 1 (stack detected) and Check 3 green for
  every detected language. A language whose smoke-parse failed downgrades
  that language's coverage to Ready-with-gaps, not Not-ready for the whole
  skill — the other languages still run.
- **`docs-drift`** — needs Check 6 to have found at least one doc file;
  otherwise Not-ready (nothing to check).
- **`ci-topology`** — needs Check 5's git-repo check to pass; Not-ready if
  the repo isn't under git.
- **`lint-audit`** — Ready-with-gaps if Check 4 found no `house-rules.md`
  (falls back to best-effort from `CLAUDE.md`), Ready if it's present.

Also write `<output_dir>/preflight_summary.json` — a small machine-
readable sidecar alongside the human-readable report, the same
human/machine split `modernize-map` uses for `topology.json`/
`TOPOLOGY.html`. This is what `self-assess-portfolio` reads to build a
multi-repo dashboard without parsing markdown:

```json
{
  "languages": [<detected languages from Check 1>],
  "houseRulesPresent": <bool from Check 4>,
  "gitRemoteCount": <count from Check 5, or 0 if not under git>,
  "verdicts": {
    "stageMap": "Ready" | "Ready-with-gaps" | "Not-ready",
    "docsDrift": "Ready" | "Not-ready",
    "ciTopology": "Ready" | "Not-ready",
    "lintAudit": "Ready" | "Ready-with-gaps"
  }
}
```

Print the table in the session too, and end with the single most
important fix if anything is red.
