---
name: self-assess-ui-audit
description: Statically audits the codebase's own UI surface — components, templates, and stylesheets (JSX/TSX, Vue/Svelte SFCs, HTML templates, CSS/SCSS) — for accessibility problems (missing alt text, form labels, accessible names; non-interactive elements used as controls; positive tabindex), semantic-markup problems (a clickable div where a button belongs, skipped heading levels, missing landmarks), and hardcoded design values (literal colors/dimensions where a design-token or CSS-variable system is used elsewhere), plus plausibly low-contrast literal color pairs as a static heuristic. Use this when the user asks to audit the UI/UX or accessibility of the code, check a11y, find hardcoded colors/spacing, or catch non-semantic markup. This is a STATIC, read-only source read — it never runs or builds the app, renders a DOM, takes screenshots, or computes a real WCAG contrast ratio. NOT language idioms/smells (self-assess-code-idiom), NOT module architecture (self-assess-arch-health), NOT house-rules compliance (self-assess-lint-audit).
---

Audit the current repository's **own UI surface** — components, templates, and
stylesheets — for three classes of problem the other self-assess skills don't
judge: **accessibility**, **semantic markup**, and **hardcoded design values**.
Like every other self-assess reporting skill it is strictly **read-only**: it
reports; a human (or `self-assess-transform-brief`'s plan → the gated fix
skills) changes code.

**Static-only, stated plainly (the v1 boundary):** this reads markup/style
*source*. It does **not** run or build the app, render a DOM, drive a browser,
take screenshots, or compute a rendered WCAG contrast ratio. Contrast findings
are `contrast-risk` heuristics on literal color pairs, for a human (or a real
contrast tool) to confirm — never asserted as a computed ratio. Runtime-only
accessibility (focus management, live regions in flight) is out of scope for a
static pass.

Scope boundaries, kept sharp:
- **vs `self-assess-code-idiom`** — that judges language idioms/smells in
  program logic; this judges the UI/markup/style surface only.
- **vs `self-assess-lint-audit`** — lint-audit checks only rules the repo wrote
  in `house-rules.md`; pass that file in so this skill can *avoid* re-reporting
  what it already governs.

## Step 0 — Load settings and detect the UI framework(s)

Read `.claude/self-assess.local.md` if it exists (see
`${CLAUDE_PLUGIN_ROOT}/references/settings.md`). If `enabled: false`, stop and
say so. Note `output_dir` (default `analysis/self-assess`) and
`skip_verification` (default `false`).

Detect the UI stack present by file extension (Glob), building a `frameworks`
list from what's actually there — never hardcode it:
- `react` — `*.jsx`, `*.tsx` (or `*.js`/`*.ts` with JSX)
- `vue` — `*.vue`
- `svelte` — `*.svelte`
- `html` — `*.html`, `*.hbs`, `*.ejs`, `*.njk` and similar server templates
- `css` — `*.css`, `*.scss`, `*.less`

If **no** UI files are present, do not invent a scan: write a short
`UI_AUDIT.md` noting **Not applicable — no UI surface detected** and an empty
`ui_audit_summary.json` (`{"frameworksScanned": [], "findings": []}`), and stop.

Also read `.claude/house-rules.md` (or `house_rules_path`) if it exists, to pass
in as `houseRules` — so the scan skips anything lint-audit already covers.

## Step 1 — Run the scan

**Preferred — Workflow orchestration.** If the **Workflow tool** is available in
this session (this skill invocation is your authorization):

```
Workflow({
  scriptPath: "${CLAUDE_PLUGIN_ROOT}/workflows/ui-audit-scan.js",
  args: { repoPath: "<repo root, usually '.'>", frameworks: [{ name: "<react|vue|svelte|html|css>" }, ...], houseRules: "<house-rules.md content, omit if absent>", skipVerification: <from settings, default false> }
})
```

It derives the applicable a11y/semantics/hardcoded-value catalog per framework
(from its hand-kept `FRAMEWORK_BRIEFS`), runs one finder per framework, then —
unless `skip_verification` is set — adversarially refutes every finding (checking
it isn't a decorative `alt=""`, an accessible name supplied on an ancestor, a
token-definition file, or generated code) before reporting, with a second
skeptical read for High-severity survivors. The finders/refuters are read-only
by design; **you** write the artifacts below from the structured result.

**Fallback** (no Workflow tool) — spawn a **ui-auditor** subagent per detected
framework: "Statically find a11y / semantic-markup / hardcoded-design-value
issues in the `<framework>` UI, with file:line evidence." Then verify each
finding yourself by reading the cited markup before including it.

## Step 2 — Write the report

Create `<output_dir>/UI_AUDIT.md`:
- **Summary** — frameworks scanned, findings by severity, findings by category
  (a11y / semantics / hardcoded-value / contrast-risk), refuted count, and a
  one-line restatement that contrast findings are static heuristics.
- **Findings table**, sorted by severity: category, kind, evidence (`file:line`),
  description, suggested fix.
- **Refuted candidates** — brief list (what looked like an issue but wasn't).
- If `injectionFlags` is non-empty, a prominent **"⚠ Instruction-shaped content
  found"** section.

Also write `<output_dir>/ui_audit_summary.json` — the machine-readable sidecar
`self-assess-status` aggregates and `self-assess-transform-brief` consumes:
`{"frameworksScanned": [...], "findingsBySeverity": {...}, "byCategory": {...},
"findings": [...]}`. `findingsBySeverity` is copied straight from the workflow's
`stats.bySeverity`; `byCategory` from `stats.byCategory`.

`findings` is the workflow's survivors reshaped to the **shared per-finding
contract** every self-assess reporting sidecar uses (`{severity, title,
evidence, category}`): `severity`, `evidence` (`file:line`), and `category`
copied as-is; `title` = the finding's `kind` slug (keep `description` and
`suggestedFix` as additional fields if you like — a consumer needing more than
the four shared fields still has them). Do **not** add a `fixability` key: a UI
finding is a mechanical, single-location fix (add an alt/label, replace a
literal with a token), so `self-assess-transform-brief` treats it as a normal
work item. Reshape what the workflow returned — do not re-derive it.

## Present

Report: frameworks scanned, findings by severity and category, refuted count,
and the static-only caveat for contrast. Suggest: `glow -p <output_dir>/UI_AUDIT.md`.
