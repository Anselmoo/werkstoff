---
name: andon-preflight
description: Checks whether the current repository has a legible multi-stage value stream and where the andon ledger should live. Detects stage/wire legibility (directly or via self-assess:stage-mapper if installed), checks for a house-rules.md andon-propose can draw defaults from, and confirms an output/ledger location is writable. Use this when the user asks "is my repo ready for andon", "can andon-loop run here", "check if andon can find my stages", or before running andon-propose, andon-verify, or andon-loop for the first time in a repo.
---

Check whether the current repository (the working directory, or a path
the user names) is ready for the andon plugin's loop, and report exactly
what to fix before it runs into it. Run every check even when an earlier
one fails — the goal is one complete readiness report, not the first
error.

This operates on the repo root in place — there is no `legacy/$1`-style
argument. If the user names a specific path, use that as the repo root
instead of the working directory.

This is plain skill logic, matching `self-assess-preflight` and
`quality-preflight`: no agent file, no Workflow script. Every check below
is a direct, local, read-only operation — there is no fan-out to
parallelize and nothing that benefits from adversarial verification, the
two conditions that justify a Workflow-orchestrated skill elsewhere in
this plugin.

## Check 0 — Load settings

Read `.claude/andon.local.md` if it exists at the repo root (`Read`
tool; not an error if absent — every setting below has a default). See
`${CLAUDE_PLUGIN_ROOT}/examples/andon.local.md` for the template and
`${CLAUDE_PLUGIN_ROOT}/references/settings.md` for the full field list.
If `enabled: false`, stop here and tell the user andon is disabled for
this repo (per the settings file) rather than running any check.
Otherwise note which non-default overrides are active (`output_dir`,
`ledger_dir`, `authorization_level`, `skip_verification`,
`lint_max_rules`) so the report can list them — every downstream skill
re-reads this same file independently, so getting this right once here
doesn't exempt them from checking it too.

## Check 1 — Stage/wire legibility

andon's whole loop depends on a legible value stream (stages + wires).
Determine how legible this repo's stream is, cheapest signal first:

1. If `self-assess` is installed (check for its plugin presence — e.g.
   whether the `self-assess:self-assess-stage-map` skill or
   `self-assess:stage-mapper` agent resolve), note that `andon-loop`'s
   own Phase 0 will dispatch `self-assess:stage-mapper` directly for
   real topology detection — full confidence available.
2. If not installed, do a cheap heuristic pass yourself: glob for common
   multi-package manifests (`package.json` workspaces, a Cargo
   workspace, multiple `pyproject.toml`/`go.mod` files, a monorepo-shaped
   directory layout). Report a rough stage count estimate and flag this
   as **reduced confidence** — `andon-loop` will fall back to the same
   minimal built-in heuristic and must clearly label its topology as
   lower-confidence than a `self-assess`-backed detection.
3. A single-package repo is not a failure — the loop degrades to one
   stage with no inter-stage wire, still useful for `andon-verify`
   strategies that don't need a stage boundary (b, c, f, g).

Report which of the three cases applies and the stage-count estimate.

## Check 2 — Ledger location writability

Determine `ledger_dir` (default `analysis/andon/ledger`, from Check 0)
and confirm the parent directory is writable — try creating it if it
doesn't exist yet (`mkdir -p` is safe and idempotent; this is the only
write this skill performs, and only to prove writability, not to
initialize a ledger — that's `andon-loop`'s Phase 1 job). If creation
fails (permissions, read-only filesystem), report it as a hard blocker
for `andon-loop`, since it cannot resume or persist without a writable
ledger location.

## Check 3 — House rules (andon-propose's default source)

Check for `.claude/house-rules.md` at the repo root, or the path named
by `house_rules_path` in the settings file. If present, report its size
and confirm it's non-empty prose. If absent, say so plainly:
`andon-propose`'s Phase 1 (propose maximally) will degrade to
codebase-only defaults with no repo-authored convention input, clearly
labeled — this plugin never invents or guesses this file.

## Check 4 — Cross-plugin dependency availability

`andon-verify` and `andon-loop` both reuse other plugins' skills/agents
by cross-plugin dispatch, and all of it is designed to degrade
gracefully, never hard-fail, when absent. Check and report presence
(best-effort — resolving a `plugin:skill`/`plugin:agent` name is not
always directly introspectable, so note "assumed available" vs.
"assumed absent" based on whether the plugin's marketplace entry or
directory is visible from this session, and let each downstream skill's
own runtime check be authoritative):

| Dependency | Used by | Degrades to |
|---|---|---|
| `self-assess:stage-mapper` (agent) | `andon-loop` Phase 0 topology detection | Built-in minimal heuristic, confidence flagged reduced |
| `self-assess:stage-mapper` (agent), Tier 3 | `andon-verify` strategy e (structural) | Tier 3 unavailable too → strategy e reports "cannot verify structurally," other strategies unaffected |
| `quality:quality-agentic-reliability` (skill) | `andon-verify` strategy d | Strategy d reports unavailable; loop continues with the other six strategies |
| `quality:quality-contract-drift`, `quality:quality-assertion-audit` (skills) | `andon-verify` strategy g | Strategy g reports unavailable; loop continues with the other six strategies |
| `LSP` tool (deferred Claude Code tool) | `andon-verify` strategy e, Tier 2 | Falls through to Tier 3 |
| Kythe/SCIP/LSIF index on disk | `andon-verify` strategy e, Tier 1 | Falls through to Tier 2, then Tier 3 |
| Hypothesis / fast-check / QuickCheck-family | `andon-verify` strategy f | Reports the missing per-language tool and which install command would add it; never fabricates a bespoke property-testing mechanism in its place |

## Report

Write `<output_dir>/PREFLIGHT.md` (`output_dir` defaults to
`analysis/andon`, overridable in the settings file): a status table (one
row per check, ✅/⚠️/❌, what was found, the fix for anything not
green), a line listing any active settings overrides from Check 0,
followed by a **Ready / Ready-with-gaps / Not-ready** verdict per
downstream skill:

- **`andon-propose`** — Ready if Check 3 found a house-rules file, else
  Ready-with-gaps (codebase-only defaults).
- **`andon-verify`** — Always at least Ready-with-gaps: strategy a
  (tribunal) has no external prerequisite. Ready-with-gaps names exactly
  which of the seven strategies are degraded per Check 4; never
  Not-ready — a repo with nothing else available still gets strategy a
  and the Detection Ladder's Rung 0/1 checks.
- **`andon-loop`** — Not-ready if Check 2 found the ledger location
  unwritable (nothing to persist to); Ready-with-gaps if Check 1 found
  reduced-confidence topology; Ready otherwise.

Also write `<output_dir>/preflight_summary.json` — a small
machine-readable sidecar alongside the human-readable report, the same
human/machine split self-assess's and quality's own `preflight_summary.json`
use:

```json
{
  "stageLegibility": "self-assess-backed" | "heuristic" | "single-package",
  "stageCountEstimate": 0,
  "ledgerDirWritable": true,
  "houseRulesPresent": false,
  "crossPluginDependencies": {
    "selfAssessStageMapper": true,
    "qualityAgenticReliability": true,
    "qualityContractDrift": true,
    "qualityAssertionAudit": true,
    "lspTool": false,
    "structuralIndexOnDisk": false,
    "propertyTestingLibs": {"python": false, "js": false, "other": false}
  },
  "verdicts": {
    "andonPropose": "Ready" | "Ready-with-gaps",
    "andonVerify": "Ready" | "Ready-with-gaps",
    "andonLoop": "Ready" | "Ready-with-gaps" | "Not-ready"
  }
}
```

Print the table in the session too, and end with the single most
important fix if anything is red.
