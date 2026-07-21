---
name: self-assess-autopilot
description: One-command auto-pilot over a live repo — runs the whole check then plan then fix then validate value stream by conducting the skills that already exist, without adding a new loop. The CHECK phase (read-only, no fixes) runs stage-map plus the reporting skills (docs-drift, ci-topology, lint-audit, code-idiom, arch-health), the UI audit, extract-rules, and — if the confab plugin is installed — its dependency/assertion/contract/agentic audits. The PLAN phase runs self-assess-transform-brief, which synthesizes every finding into one phased MODERNIZATION_BRIEF with ranked work items plus a behavior contract. The FIX-and-VALIDATE phase runs andon-loop in ingest mode, applying one gated fix per phase and proving each with andon-verify's tribunal. Plan-and-gate throughout — nothing is edited without a human approving the phase. Use this when the user asks to "run the auto-pilot", "check, plan, fix and validate", "harden this repo end to end", "do a full self-assess pass and fix what you find", or "auto-pilot mode". This skill conducts; it re-implements none of the phases.
---

Conduct the full **check → plan → fix → validate** value stream for the current
repository by dispatching the skills that already own each phase. This skill is
a **conductor**: it adds no new analysis, no new loop, and never edits code
itself — it sequences existing skills and enforces the hand-offs between them.

The division of labor is fixed:
- **`self-assess` owns check + plan** (this skill runs that half directly).
- **`andon-loop` owns fix + validate** (this skill hands the plan to it).
- **Autonomy is plan-and-gate**: the check phase is strictly read-only ("no
  fix"), and no code changes until a human approves a phase. The existing
  gates stay in force — self-assess's Edit skills are off by default, and the
  andon rule halts the loop on any unproven wire.

## Step 0 — Settings and readiness

Read `.claude/self-assess.local.md` if it exists (see
`${CLAUDE_PLUGIN_ROOT}/references/settings.md`). If `enabled: false`, stop and
say so. Note `output_dir` (default `analysis/self-assess`).

Dispatch **`self-assess-preflight`**. If it returns **Not-ready**, stop and
report what's missing (do not run a half-blind pass). If **Ready-with-gaps**,
report the gaps and continue — each downstream skill degrades on its own.

## Step 1 — CHECK (read-only; nothing is fixed here)

State to the user plainly: this phase only *reads* — it produces findings, it
changes no code. Run, reusing each skill's own Workflow orchestration:

1. **`self-assess-stage-map` first** — it writes `stage_graph.json` and
   `file_stage_index.json`, which the plan phase needs to attribute findings to
   stages. Everything else can follow once this exists.
2. Then the finding domains (independent — run as your harness allows):
   `self-assess-docs-drift`, `self-assess-ci-topology`,
   `self-assess-lint-audit`, `self-assess-code-idiom`,
   `self-assess-arch-health` (needs `stage_graph.json`),
   `self-assess-ui-audit`, and `self-assess-extract-rules` (mines the P0/P1
   rules the behavior contract is built from).
3. **confab, if installed** — dispatch `confab-dependency-audit`,
   `confab-assertion-audit`, `confab-contract-drift`,
   `confab-agentic-reliability`. Each writes a `*_summary.json` whose
   `findings` array the plan phase ingests. If confab isn't installed, say so
   and continue (its findings are simply absent from the plan, never faked).

Skip any domain that doesn't apply (e.g. `ui-audit` with no UI surface, confab
if absent) — report it as skipped, never as clean.

## Step 2 — PLAN

Dispatch **`self-assess-transform-brief`**. It reads every sidecar Step 1
produced, attributes each file:line finding to a phase via
`file_stage_index.json`, ranks work items by severity × complexity, folds
confab's `fixable` findings in as work items and its `advisory` findings into
per-phase advisory notes, and derives the per-phase **Behavior Contract** from
`extract-rules`' P0/P1 rules. Output: `MODERNIZATION_BRIEF.md` — the single
plan the fix phase runs against.

## Step 3 — GATE (plan-and-gate)

Present the brief to the user before any fix: the phase sequence, the ranked
work items per phase, the Open Questions, and — critically — any **P0-blocker
rules** (confidence below High) that must be human-confirmed before their phase
may change code. Ask the user to approve running the fix phase (all phases, or
phase-by-phase). Do **not** proceed to Step 4 without approval. If the user
only wants the plan, stop here — a brief with no execution is a valid outcome.

## Step 4 — FIX + VALIDATE (gated, per phase)

Hand the approved brief to **`andon-loop` in ingest mode**: ensure the target
repo's `.claude/andon.local.md` has `gap_source: self-assess-brief` (and
`self_assess_output_dir` pointing at this run's `output_dir`), then dispatch
`andon-loop`. It takes the stream from the brief's phases, turns each phase's
work items into gaps routed to their named fix skill
(`self-assess-idiom-fix` / `self-assess-transform-execute` /
`confab-remediator`), applies **one gated fix per phase**, and proves each
against the phase's Behavior Contract via **`andon-verify`**'s adversarial
tribunal (the named `{wire, contract, fixDiff}` entry point). The andon rule
halts on any unproven wire, blast-radius over the authorization ceiling, or an
unmet P0 blocker — surface the halt; do not force past it.

If `andon` is **not** installed, do not fabricate a fix loop: report that the
plan is ready but the fix+validate half needs the andon plugin, and stop after
Step 3.

## Step 5 — Report

Summarize the whole pass: domains checked (and skipped), the plan's phase/work-
item/behavior-contract counts, what the fix loop advanced vs halted on, and
what remains for a human — Open Questions, P0 blockers, advisory notes, and
Unattributed findings. Point the user at `MODERNIZATION_BRIEF.md`, the
`findings-dashboard.html` (via `self-assess-status`), and the andon ledger.
