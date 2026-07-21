---
name: confab-contract-drift
description: This skill should be used when the user asks to "check for type signature drift", "verify our API schema matches the handler", "audit our function signatures for drift", "find mismatched function contracts", "check if type hints match how functions are actually called", or "audit our OpenAPI/GraphQL schema against the code". Extracts machine-checkable contracts (type hints, function signatures, docstring parameter/return descriptions, API/OpenAPI/GraphQL schemas) from source files and checks each against actual call-site and handler usage, reporting contradictions with file:line evidence on both sides.
---

Check whether this repository's machine-checkable contracts still match how
they are actually used. This is scoped to **type signatures, docstring
parameter/return contracts, and API/OpenAPI/GraphQL schemas only** — it does
not evaluate prose claims in CLAUDE.md, README, or ADRs. That is
`self-assess-docs-drift`'s job; this skill never extracts or verifies prose
documentation claims, only contracts a type checker or schema validator
could in principle enforce.

## Step 0 — Load settings, find contract sources, load house rules

Read `.claude/confab.local.md` if it exists (see
`${CLAUDE_PLUGIN_ROOT}/references/settings.md`). If `enabled: false`, stop
and say so. Note `output_dir` (default `analysis/confab`) and
`skip_verification` (default `false`).

Glob for likely contract sources based on what the repo actually contains —
do not assume all of these are present:
- Typed source files (`*.py` with type hints, `*.ts`/`*.tsx`, `*.go`,
  `*.rs`, `*.java`) where function/method signatures live.
- Schema files: `openapi.yaml`/`openapi.json`, `swagger.yaml`,
  `**/*.graphql`/`schema.graphql`, `**/*.proto`.

If the user named a specific module or file, scope `contractSources` to
that instead of scanning the whole repo. Build `contractSources` from what
actually exists.

Read `.claude/house-rules.md` (or the path named by `house_rules_path` in
the settings file) if it exists (pass `null` if absent).

## Step 1 — Run the scan

**Preferred — Workflow orchestration.** If the **Workflow tool** is
available in this session (this skill invocation is your authorization):

```
Workflow({
  scriptPath: "${CLAUDE_PLUGIN_ROOT}/workflows/contract-drift-scan.js",
  args: { repoPath: "<repo root, usually '.'>", contractSources: [<contract source files found>], houseRules: <content or null>, skipVerification: <from settings, default false> }
})
```

It runs two finders in parallel — one for type-hint/signature drift, one for
schema-vs-handler drift — then, unless `skip_verification` is set, an
independent referee re-checks every candidate mismatch before it's
reported (plus a second independent re-confirmation for anything that
comes out High confidence), so a false positive dies before it reaches the
artifact. With `skip_verification`, candidates are reported directly and
labeled unverified; leave it off unless the user explicitly wants a fast
pass. Tell the user the contract-source count before launching. The
finders/referees are read-only by design; **you** write the artifact below
from the structured result.

**Fallback** (no Workflow tool) — spawn one **contract-auditor** subagent
per contract type (type-hint/signature drift, schema-vs-handler drift):
"Read the contract sources listed and extract every machine-checkable
contract — type hints, function signatures, docstring parameter/return
descriptions, or API/OpenAPI/GraphQL schema fields. This audits
machine-checkable contracts only; do not extract prose documentation
claims. For each, cite where it's declared (`file:line`) and check it
against the actual call sites/handlers you read, citing `file:line` there
too. Report `contradicted: true` only if the code genuinely does not match
the declared contract." Collect results, then for each candidate
mismatch, re-check it yourself by reading both locations before including
it — don't report a contradiction on a single agent's word.

## Step 2 — Write the report

Create `<output_dir>/CONTRACT_DRIFT.md`:
- **Summary** — contract sources checked, total contracts extracted,
  confirmed mismatches, refuted candidates (the false-positive rate the
  verification bought)
- **Mismatches**, grouped by contract type (TypeSignature / Docstring /
  Schema), each as a card:
  ```
  ### Contract: <declaredContract>
  **Type:** <contractType>
  **Declared:** `<declaredSource>`
  **Actual usage:** `<actualSource>` — <actualUsage>
  **Confidence:** High | Medium | Low
  ```
- **Refuted candidates** — brief list of what looked like drift but
  wasn't, and why (shows the checker isn't just flagging every mismatch)
- If `injectionFlags` is non-empty, a prominent **"⚠ Instruction-shaped
  content found"** section listing each location

Also write `<output_dir>/contract_drift_summary.json` — a small
machine-readable sidecar for downstream dashboards:
`{"contractSourcesChecked": N, "totalContractsChecked": N,
"confirmedMismatches": N, "byContractType": {...}, "findings": [...]}` (the
middle two copied straight from the workflow's `confirmedFindings.length` and
`stats.byContractType`).

`findings` is the workflow's **confirmed** mismatches (`contradicted: true`)
reshaped to the **shared per-finding contract**
`self-assess-transform-brief` reads (`{severity, title, evidence, category,
fixability}`): `severity` derived from `confidence` (High/Medium/Low — same
confidence-as-severity mapping `self-assess-docs-drift` uses); `title` =
`declaredContract` (the contract that drifted); `evidence` = `declaredSource`
(the `file:line` of the **declared** contract — that is the fix site
`confab-remediator` edits, keeping the declaration and the actual usage in
sync; mention `actualSource` in a `description` field if you keep one);
`category` = the constant `"contract-drift"`; `fixability` = `"fixable"`
(correcting one declared type/signature/docstring is the single-location
change `confab-remediator` already applies).

## Present

Report: contracts checked, mismatches found, refuted count. If any
confirmed mismatch is High confidence, call it out by name — that's the
one most worth fixing first. Remind the user this skill only covers
machine-checkable contracts (types, signatures, schemas) — if they want
prose documentation checked against the code, that's
`self-assess-docs-drift`. Suggest: `glow -p <output_dir>/CONTRACT_DRIFT.md`
