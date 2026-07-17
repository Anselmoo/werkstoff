# Andon vocabulary

Canonical glossary for every `andon-*` skill. Extracted from the personal
`andon-loop` skill's core-vocabulary table. Read this once; every skill in
this plugin uses these terms without redefining them.

| Term | Meaning |
|---|---|
| **Stream** | The ordered chain of stages and the wires between them — one project's whole value stream. |
| **Stage** | One service / package / build target (e.g. a Rust crate, a Python core package, a web app). |
| **Wire** | The handoff between two stages — the contract A must satisfy for B. Status: 🟢 proven · 🔴 broken/unproven · ⚪ unknown. |
| **Wired test / wire proof** | The evidence that proves a wire green: a contract/integration check across the boundary, produced by one of `andon-verify`'s seven strategies — never a unit test confined inside one stage. |
| **Andon rule** | You may not advance past a 🔴 or ⚪ wire. Stop, fix, re-prove, then advance. See `andon-loop/SKILL.md` for this plugin's three-condition stop rule built on top of this base rule. |
| **Constraint** | The stage or wire currently limiting throughput (Theory of Constraints). The loop attacks it first. |
| **Lane** | **Fast / non-visible** (JSON, schema, contract, type-level — cheap, runs every pass) vs **Slow / visible** (browser, E2E, rendered-surface, human-in-the-loop — expensive, runs on cadence or gets offloaded). Generalized in `andon-verify` as the Detection Ladder (Rung 0–4) — see `andon-verify/references/*` and its shared-cost-model note. |
| **Pass** | One left-to-right traversal of the stream. The unit the andon board scrubs over. |
| **Cycle** | A **converged run**: consecutive passes until a pass closes zero new gaps and every wire holds green. Expect 2–3+ passes per cycle. |
| **Sub-cycle** | A backtrack excursion *within* a pass: when a fix touches a contract an upstream wire depends on, jump back to re-verify (bounded to former = N−1, former-former = N−2). |
| **Cursor** | Where the loop currently is — `{stage, pass}` — recorded in the ledger so a resumed session and `andon-status`'s board both know the position. |
| **Blast radius / reversibility** | `andon-propose`'s tag on every proposed fix: `local+reversible` / `hard-to-reverse` / `shared-state-visible`. Feeds `andon-loop`'s stop-rule condition 2 — a tag exceeding the loop's current `authorization_level` (see `references/settings.md`) halts the loop rather than auto-advancing. |
| **Proof strategy** | One of `andon-verify`'s seven ways to prove a wire, selected by wire type per `andon-verify/references/wire-classifier.md`. |
| **Tier (structural evidence)** | Strategy e's confidence gradient: Tier 1 (real Kythe/SCIP/LSIF index, hard/non-overridable) > Tier 2 (live LSP tool, soft-hard/blocking-but-logged) > Tier 3 (`self-assess:stage-mapper` fallback, advisory/non-blocking only). |
| **Ledger** | Persistent state as an OKF (Open Knowledge Format) bundle under `ledger_dir` — one concept doc per stage/gap/evidence artifact, plus a `log.md` chronological history. See `andon-verify` is not the ledger owner; `andon-loop` is. Full schema: `andon-verify/references/okf-ledger-schema.md`. |

## Relationship to `andon-loop`'s phases

The vocabulary above is used across all six of `andon-loop`'s phases (detect
topology → init/resume ledger → scan stage for gaps → pick one gap by
priority → prove the wire, stop on red → advance / close pass into cycle /
self-optimize) — see `skills/andon-loop/SKILL.md` for the phase-by-phase
walkthrough. `andon-propose` owns "pick one gap by priority" (with the
blast-radius tag as a new output field); `andon-verify` owns "prove the
wire, stop on red."
