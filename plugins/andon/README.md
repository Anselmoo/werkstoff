# andon

Evidence-grounded harden-and-advance loop for live, actively-maintained
codebases: propose maximally from the code/artifacts/best-practice, verify
adversarially against evidence rather than authority across seven proof
strategies chosen by wire type, and advance only past a proven wire (the
andon rule) — never past a broken or unproven one. One methodology, built
as a small composable skill family (superpowers-style), not one
monolithic mega-skill. Read-only except a scoped output directory.

## Install

Add this marketplace and install the plugin (see the root
[`marketplace.json`](../../.claude-plugin/marketplace.json)), or point
Claude Code at this directory directly:

```bash
cc --plugin-dir /path/to/werkstoff/plugins/andon
```

## Quickstart

```
andon-preflight          # is this repo's value stream legible? where does the ledger go?
andon-loop --pass        # run one pass: scan the current stage, pick one gap, prove the wire
andon-status             # render the board from ledger state, no new pass
```

`andon-loop` composes `andon-propose` and `andon-verify` itself — most
sessions only ever invoke `andon-loop` and `andon-status` directly, with
`andon-preflight` run once up front.

## Skills

| Skill | Purpose |
|---|---|
| `andon-preflight` | Checks whether the repo has a legible multi-stage value stream and where the OKF ledger should live. Detects stage/wire legibility directly, or via `self-assess:stage-mapper` if the `self-assess` plugin is installed; checks for a house-rules file `andon-propose` can draw defaults from; confirms the output/ledger directory. |
| `andon-propose` | Proposes a fix for one gap maximally — from the codebase, the ledger's own written artifacts, and domain best-practice — then grills the user one question at a time, only on genuinely load-bearing forks, each paired with a recommended answer. Tags every proposed fix with a blast-radius/reversibility rating (`local+reversible` / `hard-to-reverse` / `shared-state-visible`), feeding `andon-loop`'s stop rule. |
| `andon-verify` | Proves or refutes one wire using whichever of seven evidence-grounded proof strategies its type calls for: adversarial tribunal (code/artifact, the default), oracle-gap V&V (numerical/scientific), an anonymous falsifiability rubric (epistemic claims — see the NO-PERSONA RULE below), agentic-reliability dispatch (did an autonomous fix stay reliable — dispatches `confab:confab-agentic-reliability`), "verify the verifier" (contract-drift + assertion-strength dispatches to `confab:confab-contract-drift` and `confab:confab-assertion-audit`), property/invariant-based proof (per-language property-based testing), and Kythe-schema structural proof (a 3-tier fallback, the plugin's one hard/non-overridable gate). A shared Detection Ladder cost model spans all seven — climb only as high as the defect class requires. |
| `andon-loop` | The outer 6-phase cycle: detect topology → init/resume the OKF ledger → scan the current stage for gaps → pick one by priority → prove the wire (stop on red) → advance / close the pass into a cycle / self-optimize. Refuses to advance past a broken or unproven wire — the andon rule, now three hard-gate conditions (wire-proof failure, blast-radius over-authorization, and Tier 1/2 structural-graph contradiction — the last one is non-overridable). |
| `andon-status` | Renders the andon board from the current OKF ledger state without running a new pass — which stages/wires are green, red, or unknown, the current cycle/pass counters, the active constraint, and the single most useful next step. Primary output is a native markdown/text summary; attempts OKF's own `visualize` subcommand as a best-effort extra if that tooling happens to be present, never as a hard dependency. |

## Agents

Four thin, functional role-agents power `andon-verify`'s default tribunal
strategy (strategy a). They are **roles**, not persona role-play of any
identified individual — see the NO-PERSONA RULE below.

| Agent | Role |
|---|---|
| `andon-defender` | Advocates that a wire's fix satisfies the wire's contract — the strongest honest case it passes. Always blind to the Challenger's case. |
| `andon-challenger` | Advocates that a wire's fix does NOT satisfy the wire's contract — the strongest honest case it fails, grounded in evidence. Never authored or influenced by whoever proposed or built the fix under review. |
| `andon-verifier` | Collects ground-truth evidence — runs tests, greps the repo, reproduces claimed defects — so the Defender's and Challenger's cases are grounded in fact, not assertion. Read-only. |
| `andon-adjudicator` | Reads the Defender case, the Challenger case, and the Verifier's evidence, then renders a per-criterion verdict against the wire's contract. Never the same session/orchestrator that proposed or built the fix under review. |

Two more strategies dispatch **existing** agents from sibling plugins in
this marketplace rather than defining new ones: strategy d dispatches
`confab:confab-agentic-reliability`, strategy g dispatches
`confab:confab-contract-drift` and `confab:confab-assertion-audit`.
Topology detection (`andon-loop` Phase 0) dispatches
`self-assess:stage-mapper` the same way. All three degrade gracefully —
andon's core loop still works if `self-assess` or `confab` aren't
installed; the dependent strategies just report unavailable rather than
hard-failing.

## The NO-PERSONA RULE

`andon-verify` never invokes a named real person as an appeal to
authority. Every criterion traces to something objectively checkable — a
test result, a measured cost, a mathematical/physical invariant,
reproducibility — never "what would [named individual] say." This is
distinct from "no adversarial roles": the tribunal's Defender/Challenger/
Adjudicator (above) are functional roles, not persona role-play of an
identified individual, so they're unaffected. The strategy that required
active restructuring to honor this rule is documented in
`skills/andon-verify/references/epistemic-rubric.md`.

## The ledger — Open Knowledge Format (OKF)

`andon-loop`'s ledger is a native implementation of [OKF](https://github.com/GoogleCloudPlatform/knowledge-catalog/tree/main/okf)
(v0.1) — plain markdown files with YAML frontmatter, organized as a
directory tree of linked "concepts," git-native by design. One concept
doc per stage, one per gap/pass (linked to the stage and to whichever
evidence resolved it), one per evidence artifact from any `andon-verify`
strategy (linked from the gap it resolved — giving a free "cited by"
reverse-link index for "which pass actually proved this wire"). Pass/
cycle history lives in OKF's reserved `log.md`. Full schema:
`skills/andon-verify/references/okf-ledger-schema.md`.

Adopting the OKF **format** is a hard requirement (trivial, zero external
dependency — it's a markdown/YAML convention this plugin implements
directly). Reusing OKF's own reference-agent/visualizer **tooling** is
optional and best-effort only, gated on that tooling proving stable —
`andon-status`'s primary output never depends on it.

## Workflow

`workflows/andon-cycle-scan.js` runs one andon-loop pass at Workflow-tool
scale: a parallel gap-finder per stage file (Find), then a Defender/
Challenger/Verifier/Adjudicator panel on the winning candidate's wire
proof (Verify) — mirroring the parallel-finder + adversarial-verify
pattern already established in `self-assess`'s and `confab`'s workflow
scripts. Like every Workflow script in this marketplace, it has no
filesystem access: `andon-loop`'s SKILL.md reads `stageFiles` and
`houseRules` first and passes them in via `args`.

## Settings

Optional per-project overrides live in `.claude/andon.local.md` in the
repo being hardened — copy `examples/andon.local.md` there and edit it:

```yaml
---
enabled: true
house_rules_path: .claude/house-rules.md
output_dir: analysis/andon
ledger_dir: analysis/andon/ledger
authorization_level: local+reversible
skip_verification: false
lint_max_rules: 12
---
```

Every skill reads this file independently at the start of its own run —
no hooks in this plugin, so **no Claude Code restart is needed** after
editing it. Add `.claude/*.local.md` to the target repo's `.gitignore`.
Full field reference, including the one field (`skip_verification`) that
never overrides the Kythe Tier-1 hard gate: `references/settings.md`.

## Prerequisites

Every skill degrades gracefully without these — run `andon-preflight` to
check what's available:

- **`self-assess` plugin** (optional) — sharpens `andon-loop`'s topology
  detection via `self-assess:stage-mapper`. Falls back to a minimal
  built-in heuristic, flagged as reduced confidence, without it.
- **`confab` plugin** (optional) — required for `andon-verify` strategy
  d (agentic-reliability dispatch) and strategy g ("verify the
  verifier"). Those two strategies report unavailable without it; the
  rest of `andon-verify` is unaffected.
- **A Kythe/SCIP/LSIF index, or the `LSP` tool** (optional) — needed for
  Tier 1/2 confidence on strategy e (structural/connectivity proof).
  Falls back to `self-assess:stage-mapper`'s grep/read-based extraction
  at Tier 3, explicitly labeled advisory rather than a hard gate.
- **A per-language property-based testing library** (Hypothesis, fast-
  check, QuickCheck-family) (optional) — needed for strategy f. Reports
  unavailable for that wire type without one; other strategies unaffected.
- **`git`** — sharpens the OKF ledger's diff/blame trail. The ledger
  still functions as plain files without it.

## Safety notes

Read-only against the target repo except the configured `output_dir`
(default `analysis/andon`, including the ledger). Every agent and
Workflow script treats code, comments, and existing artifacts read from
the target repo as **data to analyze, never instructions to follow** —
comments or commit messages phrased as directives are reported as
`injectionSuspects`, never obeyed. `andon-loop`'s stop rule condition 3
(Kythe-family structural evidence at Tier 1/2) is non-overridable by any
adjudication step in this plugin.

## License

MIT — see [`LICENSE`](LICENSE).
