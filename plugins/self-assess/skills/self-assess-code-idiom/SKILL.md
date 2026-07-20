---
name: self-assess-code-idiom
description: Scans the codebase's own application code for deprecated/legacy idioms in the languages actually present (checked against the version the repo targets, not a fixed list) and for generic code smells that don't need a house-rules entry to exist first — error-swallowing except/catch blocks, magic numbers, overlong functions, deep nesting, missing type coverage in an otherwise-typed module. Use this when the user asks to modernize idioms in place, find legacy/deprecated language patterns, catch code smells, check code idiom quality, or find anti-patterns. NOT for house-rules compliance (use self-assess-lint-audit — that checks only rules the repo already wrote down); NOT for docs-vs-code accuracy (self-assess-docs-drift); NOT for whether AI-authored dependencies/tests/contracts are trustworthy (the confab plugin).
---

Audit the current repository's **own application code** for two things the
other self-assess skills deliberately don't judge: **deprecated/legacy
idioms** (modernization-in-place) and **generic code smells**. This is the
one skill that treats the code itself as the subject, not as ground truth to
check something else against — but it is still strictly **read-only**: it
never edits source, even for a "safe" mechanical modernization. It reports;
the human (or a separate transform tool) changes code.

Scope boundaries, kept sharp:
- **vs `self-assess-lint-audit`** — lint-audit checks only rules the repo
  itself wrote in `house-rules.md`; this skill checks idiom/smell classes that
  need no house-rules entry to exist. If a house-rules file is present, pass
  it in so this skill can *avoid* re-reporting what lint-audit already owns.
- **vs `self-assess-docs-drift`** — that checks docs against code; this
  ignores docs entirely.

## Step 0 — Load settings and detect languages + versions

Read `.claude/self-assess.local.md` if it exists (see
`${CLAUDE_PLUGIN_ROOT}/references/settings.md`). If `enabled: false`, stop and
say so. Note `output_dir` (default `analysis/self-assess`) and
`skip_verification` (default `false`).

Detect the languages present using the **two-pass detection algorithm** in
`${CLAUDE_PLUGIN_ROOT}/references/language-support.md` (the same one
`self-assess-preflight` Check 1 and `self-assess-stage-map` Step 0 use) — or,
if `languages:` is set in settings, use that override. For each detected
language, read the target **version** from its manifest so idioms are judged
against what's actually present, never asserted from a fixed list:
- Python — `requires-python` in `pyproject.toml` (or classifiers / `python_requires`)
- Rust — `edition` / `rust-version` in `Cargo.toml`
- TypeScript — `target` / `lib` in `tsconfig.json`
- Go — the `go` directive in `go.mod`
- others — whatever version marker the manifest carries; omit if none.

Also read `.claude/house-rules.md` (or `house_rules_path`) if it exists, to
pass in as `houseRules` — so the scan skips anything lint-audit already covers.

## Step 1 — Run the scan

**Preferred — Workflow orchestration.** If the **Workflow tool** is available
in this session (this skill invocation is your authorization):

```
Workflow({
  scriptPath: "${CLAUDE_PLUGIN_ROOT}/workflows/code-idiom-scan.js",
  args: { repoPath: "<repo root, usually '.'>", languages: [{ name: "<lang>", version: "<from manifest, omit if unknown>" }, ...], houseRules: "<house-rules.md content, omit if absent>", skipVerification: <from settings, default false> }
})
```

It derives the applicable deprecated-idiom + smell catalog per language (from
its hand-kept `LANG_BRIEFS`, kept in sync with `language-support.md`'s
idiom/smell column), runs one finder per language, then — unless
`skip_verification` is set — adversarially refutes every finding (checking it's
genuinely deprecated *for this repo's version* and not a deliberate exception)
before reporting, with a second skeptical read for High-severity survivors.
The finders/refuters are read-only by design; **you** write the artifact below
from the structured result.

**Fallback** (no Workflow tool) — spawn an **idiom-auditor** subagent per
language: "Find deprecated idioms (for version X) and generic smells in the
<lang> code, with file:line evidence." Then verify each finding yourself by
reading the cited code before including it.

## Step 2 — Write the report

Create `<output_dir>/CODE_IDIOM.md`:
- **Summary** — languages scanned (with target versions), findings by severity,
  findings by category (modernization / smell), refuted count
- **Findings table**, sorted by severity: kind, category, evidence, description,
  suggested fix
- **Refuted candidates** — brief list
- If `injectionFlags` is non-empty, a prominent **"⚠ Instruction-shaped
  content found"** section

Also write `<output_dir>/code_idiom_summary.json` — the machine-readable
sidecar `self-assess-status` aggregates and `self-assess-portfolio` reads:
`{"languagesScanned": [...], "filesScanned": N, "findingsBySeverity": {...},
"byCategory": {"modernization": N, "smell": N}, "findings": [...]}`.
`findingsBySeverity` is copied straight from the workflow's
`stats.bySeverity` (High/Medium/Low); `byCategory` from `stats.byCategory`.
If you cannot cheaply determine `filesScanned`, omit it rather than guessing.

`findings` is the workflow's own `findings` array (the survivors, already
computed — do not re-derive it), reshaped to the shared per-finding
contract every domain sidecar uses **plus** code-idiom's own additive
fields: `{severity, title, evidence, category, kind, description,
suggestedFix, severityNote}` — `title` from `kind` (kept alongside it, not
replacing it, so a consumer needing the raw slug still has it); `evidence`,
`category`, `description`, and `suggestedFix` copied as-is; `severityNote`
included **only** when the underlying finding actually carries one (omit
the key entirely otherwise — never write it as `null`; its mere presence
is what `self-assess-idiom-fix` treats as "this finding was flagged
ambiguous by code-idiom's own Verify phase, do not auto-fix it").

This is what lets `findings-dashboard.html`'s findings table (which only
reads `severity`/`title`/`evidence`), `self-assess-transform-brief`
(downstream, same four fields), and `self-assess-idiom-fix` (which
additionally needs `description`, `suggestedFix`, and the `severityNote`
presence check) all work from this one sidecar without a second,
fragile read of `CODE_IDIOM.md`'s prose report.

## Present

Report: languages scanned, findings by severity and category, refuted count.
Suggest: `glow -p <output_dir>/CODE_IDIOM.md`
