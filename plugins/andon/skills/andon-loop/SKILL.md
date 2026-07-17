---
name: andon-loop
description: Auto-enforcing loop that walks a project's value stream — its stages and the wires between them — closing one gap per stage and refusing to advance past a broken or unproven wire (the andon rule). Composes andon-propose (pick and design the fix) and andon-verify (prove the wire) over a native OKF ledger. Use this when the user wants to "harden this repo", "run the andon loop", "scan for gaps and fix them in order", "prove this wire is proven", "resume the andon ledger", or any request to iterate a multi-stage codebase closing gaps while keeping each handoff evidence-grounded rather than assumed.
---

Walk the current repository's value stream one gap at a time, proving
each wire before advancing past it. Restructured from the personal
`andon-loop` skill's six-phase cycle, composing `andon-propose` (Phase
3) and `andon-verify` (Phase 4) rather than reimplementing their logic
inline.

This is the plugin's orchestrator — the only skill that owns the OKF
ledger (init, resume, write). `andon-propose` and `andon-verify` return
structured results; this skill is the one that persists them, the same
separation self-assess/quality keep between read-only analysis
agents/skills and the orchestrating skill that writes files.

## Step 0 — Load settings

Read `.claude/andon.local.md` if it exists (see
`${CLAUDE_PLUGIN_ROOT}/references/settings.md`). If `enabled: false`,
stop and say so. Note `output_dir` (default `analysis/andon`),
`ledger_dir` (default `analysis/andon/ledger`), `authorization_level`
(default `local+reversible`), and `skip_verification` (default `false`).

## Phase 0 — Detect topology

Determine the stream's stages and wires:

1. **Preferred — `self-assess:stage-mapper` dispatch.** If `self-assess`
   is installed, dispatch the `self-assess:stage-mapper` **agent**
   directly (cross-plugin reuse — read
   `plugins/self-assess/agents/stage-mapper.md` for its exact Find-mode
   invocation shape) once per detected language to build the real
   import/use graph and package-boundary stage clustering. This reuses
   `self-assess`'s proven manifest-collapse-bug fix rather than
   re-deriving stage/wire extraction from scratch. Confidence:
   `self-assess-backed`.
2. **Fallback — built-in minimal heuristic.** If `self-assess` is not
   installed (or its agent doesn't resolve), degrade gracefully — never
   hard-fail: glob for common multi-package manifest shapes (a
   `package.json` with `workspaces`, a Cargo workspace `Cargo.toml`, a
   directory with multiple `pyproject.toml`/`go.mod` files) and cluster
   by the shallowest directory containing each manifest. This is
   deliberately coarser than `stage-mapper`'s package-boundary rule (it
   will not catch the two-packages-one-manifest case `self-assess` exists
   to fix) — **flag every stage/wire produced this way as reduced
   confidence** in the topology report and the resulting OKF stage docs
   (do not let a heuristic-derived stage silently look as trustworthy as
   a `stage-mapper`-derived one).
3. **Single-package repo.** If neither pass finds more than one stage,
   the stream is one stage with no inter-stage wire — still a valid
   topology; downstream phases operate on that one stage's own
   contract/wire-equivalent (its public API surface) instead.

Report the detected stream (stages + wires + confidence) before moving
on. A declared stream from the user always overrides detection — honor
it verbatim.

## Phase 1 — Initialize or resume the ledger

The ledger is an OKF bundle at `<ledger_dir>` (schema:
`skills/andon-verify/references/okf-ledger-schema.md`). If
`<ledger_dir>/log.md` already exists, **resume**: read every
`stages/*.md`/`gaps/*.md`/`evidence/*.md` doc, reconstruct the cursor
(the stage/wire currently in progress — the last non-closed gap doc, or
the first stage with no green outgoing wire if none is in progress), and
report current pass/cycle counts (derived by counting `## Pass N` /
`## Cycle N converged` entries in `log.md`) plus which wires are
currently green.

If no ledger exists, **initialize**: `mkdir -p <ledger_dir>/{stages,gaps,evidence}`,
write one `type: stage` doc per detected stage (Phase 0's output),
create an empty `log.md`, and set the cursor to the first stage.

## Phase 2 — Scan the current stage for gaps

Scan only the cursor's stage and its outgoing wire. Collect gaps and
classify each:

| Field | Values |
|---|---|
| `kind` | `bug` (existing behavior broken) · `feature` (behavior absent) · `wire` (handoff broken/unproven) |
| `on_constraint` | `true` if this gap sits on or feeds the stream's current bottleneck |

Gap sources: failing/missing tests, broken/unproven wires (no evidence
doc yet, or the linked evidence doc's verdict is 🔴/⚪), `TODO`/`FIXME`/
`unimplemented!`/`raise NotImplementedError`, schema drift between
producer and consumer stages, dead or stubbed handoffs.

If the **Workflow tool** is available, use `andon-cycle-scan.js`'s Find
phase for this scan (parallel gap-finding across the stage's files) — see
`workflows/andon-cycle-scan.js` and its `meta.whenToUse` for the exact
`args` shape. Otherwise scan directly via `Glob`/`Grep`/`Read`.

**Do not fix anything yet.** Write one `type: gap` doc per gap found
(status `open`), and output the gap list for this stage only.

## Phase 3 — Pick one gap, propose the fix

Pick **one** gap using this priority order (Theory of Constraints):

1. Anything `on_constraint: true`.
2. `wire` gaps before `bug` gaps before `feature` gaps.
3. Within a tie, smallest expected blast radius first (a genuine
   pre-proposal guess — `andon-propose` assigns the authoritative tag).

Dispatch **`andon-propose`** with the chosen gap and its ledger context
(the gap's own doc, the stage's doc, any linked evidence docs). It
returns a fix description, files touched, a recommended `andon-verify`
strategy, and a blast-radius tag. Update the gap's OKF doc with the
proposal and the blast-radius tag (`tags: [..., "blast-radius:<tag>"]`).

**Stop-rule check, condition 2 (pre-emptive):** if the returned
blast-radius tag exceeds the current `authorization_level` (ordering:
`local+reversible` < `hard-to-reverse` < `shared-state-visible`), **halt
here** — do not apply the fix or proceed to Phase 4. Report the proposal
and ask for explicit confirmation to raise authorization for this one
fix, or to skip it and return to Phase 2 for a different gap.

## Phase 4 — Prove the wire (the enforcement gate)

Dispatch **`andon-verify`** with the proposed fix (strategy already
recommended by `andon-propose`; `andon-verify` re-confirms routing via
its own `wire-classifier.md` rather than blindly trusting the
recommendation). If the **Workflow tool** is available, `andon-verify`'s
strategy a (tribunal) dispatch runs through `andon-cycle-scan.js`'s
Verify phase for the adversarial duel — see that script's `meta` for the
exact shape.

**The andon rule — three hard-gate stop conditions:**

1. **Wire-proof failure** from any `andon-verify` strategy (a red 🔴
   verdict). Overridable only by a human explicitly re-running
   `andon-verify` with new evidence, or explicitly overriding this gap's
   priority to defer it — never by the loop silently advancing anyway.
2. **Blast-radius tag exceeding the loop's current authorization
   level** (already checked pre-emptively in Phase 3, re-checked here in
   case the fix's actual diff turned out broader than proposed).
3. **Kythe-family structural evidence at Tier 1/2 (`andon-verify`
   strategy e) contradicting the claimed wire.** *This is the only one
   of the three conditions that is non-overridable by adjudication* — not
   even the strategy a Adjudicator can waive a Tier 1 contradiction (see
   `skills/andon-verify/references/structural-graph-tiers.md`). A Tier 2
   contradiction is still blocking by default but may be overridden by an
   Adjudicator review with a specific, stated reason to doubt the LSP
   result.

On any stop condition firing: write the `type: evidence` doc (verdict
🔴, or the blast-radius/structural note), leave the gap `open`, **do not
advance**, and return to Phase 2 on the *same* stage. Report which
condition fired and why, in plain language.

On 🟢: write the `type: evidence` doc, link it from the gap doc
(`resolved by: [[evidence/<id>]]`), close the gap (`tags: [...,
"status:closed"]`), and advance.

**Sub-cycle backtrack.** If the fix touched a contract an upstream wire
depends on (a shared type, a schema field both sides read), mark the
affected upstream wires' evidence docs `status: unknown` (down to N−2
stages back, no further) and re-run Phase 4 on each before continuing
forward. Record a `## Sub-cycle` entry in `log.md`. If the same wire
reopens three times, stop treating it as a sub-cycle — it is now the
stream's constraint; escalate rather than keep backtracking.

## Phase 5 — Advance, close passes into a cycle

Move the cursor to the next stage, repeat Phases 2–4. When the cursor
wraps past the last stage, the **pass** is done. Append a `## Pass N
(cycle M)` entry to `log.md` (per the format in
`okf-ledger-schema.md`).

**Convergence.** A cycle is complete only when a pass closes zero new
gaps and every wire is green. If not, wrap the cursor back to the first
stage and run another pass — same cycle, next pass. `cycle` increments
only when a converged run ends and a fresh scan begins. Budget for 2–3+
passes; one is rarely enough.

On convergence, append a `## Cycle N converged after P passes` entry to
`log.md` (the OKF-native cycle report) and report it to the user.

## Phase 6 — Self-optimize between cycles

1. **Recompute the constraint** — the stage/wire most often reopened
   (sub-cycle thrash signal) or slowest to prove.
2. **Decide the next cycle's intent**: harden (wires unstable) vs.
   feature (wires green, budget intact) vs. split (fast/slow lanes have
   diverged enough to warrant different cadences).
3. **Stop condition.** If a full cycle converges in a single pass with
   zero gaps closed, the stream is hardened — hand back to the user
   rather than spinning.

## Cross-plugin degradation summary

| Dependency | Used for | Absent → |
|---|---|---|
| `self-assess:stage-mapper` | Phase 0 topology | Built-in heuristic, confidence flagged reduced (never hard-fail) |
| `quality:quality-agentic-reliability`, `quality:quality-contract-drift`, `quality:quality-assertion-audit` | `andon-verify` strategies d/g | Those strategies report unavailable for the wire; loop continues with applicable remaining strategies |
| Workflow tool | Phase 2 parallel scan, Phase 4 tribunal duel | Direct sequential dispatch via `Skill`/`Agent` tools instead |

None of these ever hard-fail the loop itself — only the specific
capability they back degrades, clearly labeled.

## Output format

Per working session, deliver in this order:

1. **Stream map** (once, or when it changes) — stages, wires, confidence.
2. **Ledger delta** — cycle/pass counters, wire statuses since last run.
3. **This step** — the gap picked, why, the proposed fix, the wire-proof
   result, and the andon verdict (advanced / halted, and which stop
   condition if halted).
4. **At cycle close** — the cycle report and the next constraint.
