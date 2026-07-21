---
name: confab-assertion-audit
description: This skill should be used when the user asks to "check if our tests actually assert anything", "run a mutation-testing pass", "find assertion-free tests", "check our test suite's assertion strength", or wants to know whether AI-generated tests genuinely catch bugs rather than merely executing code for coverage. Proposes plausible small mutations to a target module's logic and determines — via LLM reasoning or, if a real mutation-testing tool is available, ground-truthed against that tool — whether the existing test suite would actually catch each one.
---

Check whether a target module's **test suite actually catches bugs**, not
just whether it runs the code. Coverage tells you code executed; this
skill tells you whether anything would have failed if the logic were
subtly wrong — the exact gap LLM-generated tests are prone to leaving
open (they reach reasonable coverage while asserting little).

## Step 0 — Load settings and pick a target

Read `.claude/confab.local.md` if it exists (see
`${CLAUDE_PLUGIN_ROOT}/references/settings.md`). If `enabled: false`, stop
and say so. Note `output_dir` (default `analysis/confab`).

This skill has no `skip_verification` fast path, even though the shared
settings file defines that field for other confab skills — the
independent re-derivation of "would the tests catch this mutation" is
the finding itself, not an optional precision/speed tradeoff, so it is
never skippable here. If the user asks to skip it anyway, explain why and
proceed with verification regardless.

Determine the target: honor a user-specified file/module; otherwise
prefer recently-changed files (`git diff`/`git log`, read-only) over a
full-repo sweep, and ask before falling back to a full-repo scan.

If `<output_dir>/preflight_summary.json` exists (written by
`confab-preflight`), read its `mutationToolPresent` field — a
per-ecosystem boolean map (`{"python": bool, "jsTs": bool,
"javaKotlin": bool}`). Determine the target file's ecosystem from its
extension (`.py` → `python`; `.js`/`.ts`/`.jsx`/`.tsx` → `jsTs`;
`.java`/`.kt` → `javaKotlin`) and, if that ecosystem's flag is `true`,
derive the tool name yourself per `confab-preflight`'s own Check 3
mapping (`python` → `mutmut`, `jsTs` → `stryker`, `javaKotlin` → `PIT`)
to pass as `mutationTool`. If the file doesn't exist, the field is
absent, or the target's ecosystem flag is `false`, proceed in
LLM-reasoned mode; note in the final report that running
`confab-preflight` first can sharpen this audit with ground-truth
mutation scores where a real tool is available for the target language
— the same graceful-degradation discipline `self-assess-lint-audit`
uses for its `ruff` fallback.

## Step 1 — Run the scan

Enumerate `targetFiles` (the module(s) under audit) and `testFiles`
(their associated test files, via `Glob` on the project's test-naming
convention, e.g. `**/test_*.py`, `**/*.test.js`, `**/*_test.go`) — the
calling skill does this, not the workflow script, which has no
filesystem access.

**Preferred — Workflow orchestration.** If the **Workflow tool** is
available in this session (this skill invocation is your authorization):

```
Workflow({
  scriptPath: "${CLAUDE_PLUGIN_ROOT}/workflows/assertion-audit-scan.js",
  args: { repoPath: "<repo root, usually '.'>", targetFiles: ["<path>", ...], testFiles: ["<path>", ...], mutationTool: "<from Step 0, or omit>" }
})
```

It runs one finder per target file — proposing 1-3 plausible small
mutations per function (off-by-one, boundary flip, condition negation)
and an initial claim on whether the test suite would catch each — then
independently re-derives every claim in a Verify phase, never trusting
the finder's own assessment. If `mutationTool` was passed, each finder
attempts it first (real-tool mode) and only falls back to LLM reasoning
per-file if the tool is unavailable or errors on that file; every finding
carries a `toolSource` field so the two modes are never blended silently.
The finder/verifier agents are read-only by design; **you** write the
artifact below from the structured result.

**Fallback** (no Workflow tool) — spawn an **assertion-auditor** subagent
in Find mode: "Propose plausible mutations for these functions and claim
whether the test suite would catch each." Then spawn it again in Verify
mode per finding to independently re-derive the claim yourself before
including it — do not report a Find-mode claim unverified.

## Step 2 — Write the report

Create `<output_dir>/ASSERTION_AUDIT.md`:
- **Summary** — **mode, labeled prominently at the top** (`LLM-reasoned`
  or `Real-tool-augmented (tool: <name>)`), and if real-tool mode was
  requested but fell back for some files, say so explicitly rather than
  presenting a mixed run as uniformly tool-verified. Also: target files
  checked, findings by severity, refuted count, tool-invocation stats
  (attempted/succeeded) when `mutationTool` was set.
- **Findings table**, sorted by severity: function (`file:line`),
  mutation description, expected catching test (or "none found"),
  severity, mode (`toolSource`)
- **Refuted candidates** — brief list (the test suite actually catches
  it, or the original claim didn't hold up on independent re-read)
- If `injectionFlags` is non-empty, a prominent **"⚠
  Instruction-shaped content found"** section

Also write `<output_dir>/assertion_audit_summary.json` — a small
machine-readable sidecar: `{"mode": "llm-reasoned"|"real-tool-augmented",
"mutationTool": "..."|null, "targetFilesChecked": N, "findingsBySeverity":
{...}, "findings": [...]}`. `findingsBySeverity` is copied straight from the
workflow's own `stats.bySeverity`.

`findings` is the workflow's survivors reshaped to the **shared per-finding
contract** `self-assess-transform-brief` reads (`{severity, title, evidence,
category, fixability}`): `severity` as-is; `title` = `mutationDescription`
(the specific mutation the tests would miss); `evidence` = `function` (the
mutated function's `file:line`); `category` = the constant
`"weak-assertion"`; `fixability` = `"advisory"` — **always**, never
`"fixable"`. A weak-assertion finding must never become an auto-fixable work
item: a generated assertion has no ground truth beyond the module's current
(possibly buggy) behavior, which is exactly why `confab-remediator`
hard-blocks all assertion findings. `self-assess-transform-brief` routes
`advisory` findings into a phase's advisory-notes list, not its work items.

## Present

Report: mode (never blended), target files checked, findings by
severity, refuted count. If mode is LLM-reasoned and a real mutation
tool is available for the target language but wasn't detected, suggest
running `confab-preflight` first. Suggest:
`glow -p <output_dir>/ASSERTION_AUDIT.md`
