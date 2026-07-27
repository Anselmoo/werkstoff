---
name: confab-contract-drift
description: "Use when the user asks to audit type signatures, docstrings, or API/OpenAPI/GraphQL schemas against actual call-site or handler usage, wants to check for contract drift after a refactor, or wants confab's contract-drift audit run. Verification runs by default and only skips if the user explicitly says skip_verification."
---

Find drift between machine-checkable contracts (type hints, function
signatures, docstring parameter/return descriptions, API/OpenAPI/GraphQL
schemas) and how code actually uses them. Never extract or verify prose
documentation — only structural, machine-checkable declarations.

## Steps

1. Determine `repo_root`, the contract source files (typed source, schema
   files) to scan, and any house rules the user mentioned. Determine
   `skip_verification`: **default `false`**. Only treat it as `true` if
   the user explicitly said so in this request — silence, "just run it
   quickly," or similar is NOT an explicit `true`.
2. Optionally build/reuse a symbol index (see "Shared symbol index" in
   `confab-assertion-audit`'s SKILL.md — the same single-flight rule
   applies here).
3. Dispatch the `contract-auditor` agent in **Find mode**: give it the
   contract source files and symbol index. Ask for `{"findings": [...]}`
   where each finding includes `declaredLocation` and
   `actualUsageLocation` (both `file:line`) in addition to the shared
   schema fields. Write its output to a scratch JSON file.
4. Unless `skip_verification` is `true`: dispatch the `contract-auditor`
   agent again in **Verify mode**, independently re-checking each
   Find-phase finding. Write `{"findings": [{"evidence": "...",
   "confirmed": true|false}, ...]}` to a second scratch file.
5. Run:
   ```
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/contract_drift.py" <repo_root> \
       --find-json <path-from-step-3> \
       [--verify-json <path-from-step-4>] \
       [--skip-verification]
   ```
   Pass `--skip-verification` ONLY if step 1 determined it should be
   `true` — in that case, omit `--verify-json` entirely (there is nothing
   to verify). Otherwise `--verify-json` is required; the script refuses
   to run without it when `--skip-verification` is absent.
   The script maps `confidence: "High"` findings to `severity: "High"`
   and writes `analysis/confab/reports/CONTRACT_DRIFT.md` and
   `analysis/confab/contract_drift_summary.json`.
6. Report the finding count to the user, and if `skip_verification` was
   `true`, say so explicitly in your summary — an unverified contract-
   drift report is weaker evidence and the user should know which one
   they got.

## What NOT to do

- Do not default to skipping verification for speed — it must be an
  explicit user request, every time, not an assumption you make on their
  behalf.
- Do not report a docstring-only observation as a contract mismatch if it
  isn't tied to an actual type hint, signature, or schema — that's prose
  documentation drift, out of this skill's scope.
