---
description: Environment readiness check — analysis tooling, documented-convention sources, git history depth, build/test toolchain
argument-hint: <area-dir>
---

Check whether this environment is ready to scan — and eventually align —
`$1`, and tell the user exactly what to fix before the other commands run
into it. Harmonization sessions fail late and confusingly when this isn't
done: pattern derivation is unreliable without git history, alignment can't
be proven safe without a working test suite, and `/consistency-canonize`
silently re-derives a rule that was already documented if nobody looked.

Run every check even when an early one fails — the point is one complete
readiness report, not the first error.

## Check 0 — Ask the human (these answers are not in the source)

Before any automated check, ask the person running this command:

1. **Scope** — Is `$1` the whole area you want harmonized, or one slice of
   a larger codebase? If a slice: is anything under it owned by another
   team or explicitly off-limits this pass?
2. **Build & test locally** — Can this environment run the test suite and
   the linter/formatter locally? `/consistency-verify` needs this to prove
   an alignment pass changed nothing observable — without it, verification
   degrades to a diff review with no executable proof.
3. **Prior attempts** — Has anyone tried to unify style/architecture here
   before? What went wrong, and is there a half-finished style guide or
   abandoned lint config lying around that should be treated as intent
   rather than as one more variant to average away?
4. **Off limits** — Is any subdirectory frozen, generated, vendored, or
   owned by another team and therefore not eligible for `/consistency-align`
   even if it diverges?

Ask, then do not block on the answers — proceed to the checks below and
record whatever came back by the time the report is written. An unanswered
question goes into the report **verbatim, marked open** — never dropped.

## Check 1 — Detect the stack

Fingerprint `$1` from file extensions and manifests: languages, frameworks,
package managers. This drives which linters/formatters in Check 2 apply,
and lets `/consistency-canonize` route documentation lookups (e.g. Python
→ `pyproject.toml` tool sections; JS/TS → `.eslintrc`/`.prettierrc`).

## Check 2 — Analysis tooling

| Tool | Used by | Without it |
|---|---|---|
| `scc` (or `cloc`) | scan | file/LOC counts fall back to `find`+`wc` |
| the repo's own linter (`ruff`, `eslint`, `golangci-lint`, `checkstyle`, …) | scan, canonize | mechanical style facts fall back to grep-based heuristics — noisier, more false positives |
| the repo's own formatter (`black`, `prettier`, `gofmt`, …) | align | formatting-only diffs can't be auto-normalized as a free first pass; every stylistic edit goes through the slower pattern-alignment path instead |
| `git` with real history | scan, canonize | maturity/recency weighting (Check 5) is unavailable; canonize falls back to frequency-only weighting and flags every derived rule as lower-confidence |

Include the platform's install one-liner for anything missing.

## Check 3 — Build & test toolchain (prove it, don't just check presence)

Identify the test runner and formatter/linter entry points from the
manifest, then **run them once against the unmodified tree**:

- Run the test suite (or a representative subset) and record pass/fail
  counts and wall-clock time. This is the baseline `/consistency-verify`
  diffs against later — a passing baseline here is the precondition for
  every later equivalence claim.
- Run the linter/formatter in check-only mode (`--check`, `--dry-run`) and
  record its current finding count. A run that fails outright (missing
  config, tool crash) is reported now, not discovered mid-`/consistency-align`.

If the test suite cannot run at all (no test framework, broken environment),
say so plainly: `/consistency-verify` will degrade to a structural diff
review with no executable proof, and `/consistency-align` should stay
scoped to low-risk, mechanically-reversible changes (formatting, naming,
docstring shape) until that's fixed.

## Check 4 — Documented-convention sources (feeds `/consistency-canonize` Step 1)

Look for anything that already states a convention explicitly — these
override derivation entirely, and a rule found here is out of
`codebase-consistency`'s scope to re-derive:

- `CLAUDE.md`, `.claude/house-rules.md`, `CONTRIBUTING.md`, ADRs under
  `docs/adr/` or similar
- Linter/formatter configs (`.eslintrc*`, `pyproject.toml` `[tool.ruff]`,
  `.editorconfig`, `rustfmt.toml`, …) — these are documentation, just
  machine-readable
- Any existing style guide, even a partial or stale one

Report what was found and where. If a person-run `self-assess` (or
equivalent convention-auditing tool) is already installed in this project,
note that documented-rule *violations* are its job, not this plugin's —
`codebase-consistency` only derives rules for what none of these sources
cover.

## Check 5 — Git history depth (feeds maturity/recency weighting)

- Is `$1` under git with meaningful history (not a fresh shallow clone)?
- Roughly how far back does history go, and how many distinct authors
  have touched the area? Sparse or squashed history degrades the
  maturity signal in `/consistency-canonize` Step 2 — report that
  degradation now rather than silently producing lower-quality derivations
  later.

## Check 6 — Scope boundary

Same concern as a legacy-modernization preflight, simpler resolution: is
`$1` a directory boundary that some *other* tooling (a separate lint
config, a separate CI job, a separate CODEOWNERS entry) treats as its own
domain? If so, note it — `/consistency-align` must not silently reach
across an owned boundary to "fix" someone else's area.

## Report

Write `analysis/$1/PREFLIGHT.md`: the Check 0 answers verbatim, a status
table (✅/⚠️/❌ per check, what was found, the fix for anything not green),
and a **Ready / Ready-with-gaps / Not ready** verdict per command:

- `scan` + `map` — need Check 1 and a rough Check 2 pass; degrade gracefully otherwise
- `canonize` — needs Check 4 (documented sources) and benefits heavily from Check 5 (git history); a red Check 5 downgrades every derived Pattern Card's confidence, not the command itself
- `brief` — needs only the discovery artifacts; no tooling
- `align` — needs Check 3 green for the **verify** step to mean anything; a red Check 3 doesn't block `align` but every applied change is unverified until fixed
- `verify` — needs Check 3 green; degrades to structural diff review otherwise

Print the table in the session too, and end with the single most important
fix if anything is red.
