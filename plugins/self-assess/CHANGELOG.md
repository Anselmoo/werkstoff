# Changelog

All notable changes to this plugin will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **`self-assess-autopilot`** skill — a one-command conductor for the full
  **check → plan → fix → validate** value stream, built on the
  division-of-labor design: self-assess owns check + plan, `andon-loop`
  (ingest mode) owns fix + validate. It dispatches the read-only checks
  (stage-map + reporting domains + `ui-audit` + `extract-rules` + confab's
  audits if installed), runs `self-assess-transform-brief` to produce one
  phased `MODERNIZATION_BRIEF.md`, gates on human approval, then hands the
  brief to `andon-loop`. Adds **no** new loop and re-implements no phase —
  it conducts existing skills. Plan-and-gate throughout.
- **`self-assess-ui-audit`** skill + `ui-auditor` agent + `ui-audit-scan.js`
  workflow — the first skill that judges the repo's **UI surface**. A
  **static, read-only** audit (no running app, no screenshots, no computed
  contrast) of components/templates/stylesheets for accessibility
  (missing alt/labels/accessible names, non-interactive controls, positive
  tabindex), semantic markup (clickable div-where-button-belongs, skipped
  headings, missing landmarks), and hardcoded design values (literal
  colors/dimensions where tokens/CSS vars are used elsewhere), plus
  `contrast-risk` heuristics. Emits `ui_audit_summary.json` in the shared
  per-finding contract, so `self-assess-transform-brief` and the
  findings dashboard consume it for free. Now a first-class dashboard domain.
- **`self-assess-transform-brief`** now also ingests **confab**'s four audit
  sidecars and the new `ui_audit` sidecar as work items, honoring a
  `fixability` flag — confab's `advisory` findings (weak assertions, agentic
  redesigns) become per-phase **Advisory notes** rather than auto-actionable
  work items. Work items are tagged with their fix owner
  (`self-assess-idiom-fix` / `self-assess-transform-execute` /
  `confab-remediator`) so the fix loop routes them.

- **`self-assess-code-idiom`** skill + `idiom-auditor` agent — the first
  skill that judges the application code itself: deprecated/legacy idioms
  (modernization-in-place, version-aware) and generic code smells that need
  no house-rules entry to exist. Per-language idiom catalog in
  `references/language-support.md`.
- **`self-assess-arch-health`** skill + `arch-health-auditor` agent — a new
  analysis pass over `self-assess-stage-map`'s graph flagging god-modules,
  circular dependencies, and layering violations as pass/fail findings
  (deterministic candidate generation + adversarial confirmation).
- **`self-assess-ci-topology`** — new commit-signing finder: flags
  inconsistent commit provenance (the green "Verified" vs grey "Unverified"
  badge — mixed signed/unsigned history, or `commit.gpgsign` unset).
- **`self-assess-idiom-fix`** skill + `idiom-remediator` agent — the
  plugin's second Edit exception (alongside `self-assess-transform-execute`).
  Applies exactly the eligible `modernization`-category findings from
  `self-assess-code-idiom`'s sidecar (mechanical, single-location rewrites
  like `Optional[X]` to `X | None`); off by default
  (`idiom_fix.mode: propose`); never touches `smell`-category findings or
  findings flagged with a `severityNote`; never verifies its own output —
  every fix, no exception, gets an explicit hand-off to `andon-verify`'s
  adversarial tribunal. `self-assess-code-idiom`'s sidecar `findings[]`
  entries were additively enriched (`kind`/`description`/`suggestedFix`/
  `severityNote`) to support this — the dashboard-required fields are
  unchanged.
- **`self-assess-transform-brief`** skill — synthesizes `self-assess-stage-map`'s
  graph and `self-assess-arch-health`'s findings into a transformation plan:
  a current→target component mapping (Keep/Merge/Split per stage, with
  merge/split rationale flagged as Open Questions rather than guessed), a
  leaf-first phased sequence, and best-practice rationale. Read-only and
  plan-only — see its **Handoff** section for why executing a phase is a
  separate, explicitly-authorized step rather than something this skill
  does itself. Emits this repo's first Mermaid (`.mmd`) artifacts and feeds
  the phase sequence into the topology viewer's previously-always-empty
  `flows` walkthrough. **Now also the reporting→plan bridge:** it absorbs the
  reporting domains' file:line findings (`code-idiom`/`lint-audit`/
  `docs-drift`) as concrete **per-phase work items** — attributed to a phase
  by looking each finding's file up in `self-assess-stage-map`'s new
  `file_stage_index.json`, ranked by severity × complexity (from
  `complexity-score`) — and derives a **per-phase Behavior Contract** from
  `self-assess-extract-rules`' P0/P1 rules (each with a characterization- or
  contract-test validation strategy; a P0 rule below High confidence is a
  phase blocker). Findings whose file has no stage fall to an explicit
  Unattributed bucket — never silently dropped. This reverses the skill's
  former deliberate refusal to map file:line findings to stages: it is now a
  lookup against a published index, not a re-derivation.
- **`file_stage_index.json`** (from `self-assess-stage-map`) and
  **`business_rules.json`** (from `self-assess-extract-rules`) — two new
  machine-readable sidecars the bridge above consumes. The former is a flat
  `{file: stage}` lookup serialized from clustering the workflow already did
  (graph-participating files only; isolated files are absent by design); the
  latter projects the confirmed P0/P1 rules with their `source` location and
  priority. Neither is a dashboard domain — both are transform-brief inputs.
- **`self-assess-transform-execute`** skill + `transform-executor` agent —
  the first of what are now two Edit/Write exceptions (`self-assess` was
  100% read-only before this; see the `self-assess-idiom-fix` entry above
  for the second). Applies exactly one already-authorized phase from
  `MODERNIZATION_BRIEF.md`; off by default (`transform.mode: plan`), gated
  per-phase (`transform.authorized_phases`), refuses a phase whose Open
  Question isn't resolved by a human first, has no `Bash`, never commits or
  pushes, and — critically — never verifies its own output: always hands off
  to `andon-verify`'s adversarial tribunal (or `andon-loop`) rather than
  self-reviewing. See `README.md`'s **Safety notes** for the full gate.
- The 5 problem-finding domain sidecars (`code_idiom`, `arch_health`,
  `lint_audit`, `docs_drift`, `ci_topology`) now additionally emit a
  `findings: [{severity, title, evidence, category}]` array — the workflows
  already computed this data, only the sidecar-write step was dropping it.
  Enables `findings-dashboard.html`'s per-finding table rows (previously
  dead code waiting for exactly this) and is what `self-assess-transform-brief`
  reads. `self-assess-extract-rules` deliberately excluded — it mines
  business rules (knowledge artifacts), not defects.

### Changed

- **`self-assess-stage-map`** now also persists the full graph as
  `stage_graph.json` (complete wire `edgeCount`s), which
  `self-assess-arch-health` consumes instead of re-deriving the import graph.
- Dashboard (`findings-dashboard.html`), `self-assess-status`,
  `self-assess-portfolio`, and `self-assess-preflight` wired for the two new
  domain sidecars (`code_idiom_summary.json`, `arch_health_summary.json`).

## [0.1.0]

- Initial release.
