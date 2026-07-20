---
name: self-assess-arch-health
description: Analyzes the real stage/wire graph self-assess-stage-map already built for architecture deficiencies — god-modules (a stage most others depend on, a bottleneck), circular dependencies between stages, and layering violations (a production stage importing a test-only/benchmark/fixture stage). Use this when the user asks to check architecture health, find god-modules or god-objects, detect dependency cycles between modules/packages, find layering or dependency-direction violations, or check whether the module boundaries are healthy. Depends on self-assess-stage-map having run first (it reads that skill's stage_graph.json, never re-deriving the graph). NOT a complexity/size ranking (use self-assess-complexity-score — that never emits pass/fail findings); NOT graph construction (self-assess-stage-map builds the graph, this judges it).
---

Judge the architecture the current repository actually has — as a set of
**pass/fail deficiency findings** over the stage/wire graph
`self-assess-stage-map` already built. This is deliberately distinct from
`self-assess-complexity-score` (which ranks stages by size with no findings and
no verdict) and from `self-assess-stage-map` itself (which *builds* the graph
and never flags a deficiency in it). Strictly **read-only**: it reports; it
never edits source.

Three deficiency classes, all computed from the graph, then confirmed against
the real code:
- **God-module** — a stage coupled to an outsized share of all other stages
  (high fan-in/fan-out): a bottleneck every change risks touching.
- **Cycle** — a set of stages that import each other (a strongly-connected
  component of size ≥ 2): none can be built, tested, or released independently.
- **Layering violation** — a production stage importing a test-only / benchmark
  / example / fixture stage: shipped code reaching into test scaffolding.

## Step 0 — Load settings and the graph

Read `.claude/self-assess.local.md` if it exists (see
`${CLAUDE_PLUGIN_ROOT}/references/settings.md`). If `enabled: false`, stop and
say so. Note `output_dir` (default `analysis/self-assess`) and
`skip_verification` (default `false`).

`Read` `<output_dir>/stage_graph.json` (the full-graph sidecar
`self-assess-stage-map` writes in its Step 2 — the `{stages, wires, deadEnds,
observations}` object, **not** the viewer-format `stage_map.json`, which only
keeps a 5-edge sample per wire and can't give accurate fan-in/fan-out).

If `stage_graph.json` does **not** exist, do not invoke the workflow. Degrade
gracefully: write a short `ARCH_HEALTH.md` and `arch_health_summary.json` (zero
findings) noting this is **Ready-with-gaps — run `self-assess-stage-map` first**,
and tell the user to run stage-map, then re-run this skill. This mirrors the
`self-assess-preflight` verdict for `arch-health`.

## Step 1 — Run the analysis

**Preferred — Workflow orchestration.** If the **Workflow tool** is available in
this session (this skill invocation is your authorization):

```
Workflow({
  scriptPath: "${CLAUDE_PLUGIN_ROOT}/workflows/arch-health-scan.js",
  args: { repoPath: "<repo root, usually '.'>", stageGraph: <parsed contents of stage_graph.json>, skipVerification: <from settings, default false> }
})
```

It computes god-module / cycle / layering candidates **deterministically** from
the graph (degree thresholds, strongly-connected components, production→test
edges — the same deterministic-analysis-then-adversarial-confirm split
`self-assess-stage-map` uses for wires), then — unless `skip_verification` is
set — has one adversarial confirmer per candidate read the actual repo to rule
out a legitimate shared kernel, an acyclic-after-all relationship, or a
mislabeled stage. The confirmers are read-only by design; **you** write the
artifact below from the structured result.

**Fallback** (no Workflow tool) — spawn an **arch-health-auditor** subagent:
"Here is the stage/wire graph `{stages, wires, deadEnds}`; find god-modules
(high fan-in/out), cycles (mutually-importing stages), and layering violations
(production→test edges), then confirm each against the real code." Verify each
finding yourself by reading the cited stages before including it.

## Step 2 — Write the report

Create `<output_dir>/ARCH_HEALTH.md`:
- **Summary** — stages analyzed, findings by severity, findings by category
  (god-module / cycle / layering-violation), refuted count
- **Findings table**, sorted by severity: category, stage(s), description,
  suggested fix
- **Refuted candidates** — brief list (a useful negative signal: the graph
  looked deficient here but the code confirmed otherwise)
- If `injectionFlags` is non-empty, a prominent **"⚠ Instruction-shaped
  content found"** section

Also write `<output_dir>/arch_health_summary.json` — the sidecar
`self-assess-status` aggregates and `self-assess-portfolio` reads:
`{"stagesAnalyzed": N, "findingsBySeverity": {...}, "byCategory":
{"god-module": N, "cycle": N, "layering-violation": N}, "findings": [...]}`.
`findingsBySeverity` is copied straight from the workflow's
`stats.bySeverity` (High/Medium/Low); `byCategory` from `stats.byCategory`.

`findings` is the workflow's own `findings` array (already computed — do
not re-derive it), reshaped to the shared per-finding contract every domain
sidecar now uses: `{severity, title, evidence, category}` — `title` from
`category` (god-module / cycle / layering-violation), `evidence` and
`category` copied as-is. Feeds `findings-dashboard.html`'s findings table
and `self-assess-transform-brief`.

## Present

Report: stages analyzed, findings by severity and category, refuted count. If
you degraded to "run stage-map first", say that plainly. Suggest:
`glow -p <output_dir>/ARCH_HEALTH.md`
