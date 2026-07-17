# Compass pipeline data-contract cheatsheet

Every cross-phase data shape in the `compass-solve` pipeline, as actually
implemented — read this before modifying any workflow script or
cross-skill data shape. Contract version: matches `plugin.json`'s
`"version": "0.1.0"` (see `../.claude-plugin/plugin.json`).

## Clarify output

Producer: `solve-orchestrate.js`'s `CLARIFY_SCHEMA` (lines 142-174), one
agent dispatch applying `compass-clarify-scope`'s methodology.

Raw schema (snake_case, what the dispatched agent returns):
```
{
  scoped_task: string,
  known_facts: [{fact: string, confident: boolean}],
  flagged_uncertainties: [{
    element: string,
    default_interpretation: string,
    confidence: number,       // 0-100
    other_readings: string,
    blocking: boolean         // orchestrator-specific extension, not
                               // part of compass-clarify-scope's base
                               // output contract
  }],
  success_criteria: [{criterion: string, status: string}]  // "stated" | "inferred" | "missing — needs elicitation"
}
```

Mode A return shape (camelCase — what `compass-solve/SKILL.md` and every
downstream consumer actually reads, `solve-orchestrate.js:217-225`):
```
{
  phase: "clarify",
  scopedTask: string,
  knownFacts: [...],
  flaggedUncertainties: [...],
  successCriteria: [...],
  needsUserInput: boolean,          // true if any flaggedUncertainties[i].blocking === true
  blockingUncertainties: [...]      // the subset where blocking === true
}
```

Consumed by: `compass-explore-branches` (`scopedTask` as `scopedProblem`),
`compass-decompose-chain` (`scopedTask` as its no-branch-exploration
input), `compass-draft-revise` (`successCriteria` as its criteria table's
starting point).

## Branch shape

Producer: `explore-branches-scan.js`'s Score-phase loop (lines 145-161).

```
{
  name: string,
  description: string,
  angle: string,             // the ANGLE_POOL key this branch was proposed under
  scores: {feasibility: number, impact: number, risk: number},  // each clamped [1,10]
  total: number,              // feasibility + impact + risk, NOT risk-inverted
  blocker: string
}
```

Consumed by: `compass-solve/SKILL.md` Step 2 (`selected` branch's
`description` becomes `selectedApproach`), `compass-decompose-chain`
(selected-approach input contract).

## Stage contract

Producer: `compass-decompose-chain/SKILL.md` Step 2, validated against
`solve-orchestrate.js`'s `DECOMPOSE_SCHEMA` (lines 241-262) and
`computeWaves()` (lines 103-129).

```
{
  id: string,              // short kebab-case slug, unique within the decomposition
  name: string,
  inputContract: string,   // exact fields/artifact consumed + concrete source
  outputContract: string,  // exact fields/artifact produced
  dependsOn: string[]      // ids of stages this stage's input actually draws from; [] = entry point
}
```

Consumed by: `solve-orchestrate.js`'s Execute phase (topological-sort
waves via `computeWaves()`), `reasoning-trace-viewer.html` (renders
`dependsOn` edges).

## Stage execution result

Producer: `solve-orchestrate.js`'s `STAGE_SCHEMA` (lines 360-372), one
agent dispatch per stage.

```
{
  modesUsed: string[],   // compass-* skill id(s) actually applied, e.g. ["compass-ground-evidence"]; [] if none needed
  output: string,        // the stage's deliverable, matching its output contract
  notes: string          // assumptions made, refusals issued, escalations taken
}
```

Stored internally as `{stage, output, modesUsed, notes}` per stage id in
`stageResultsById` (`solve-orchestrate.js:420-421`); returned to the
caller as the `stageResults` array (`solve-orchestrate.js:539`).

## `dag` object

Producer: `solve-orchestrate.js` (lines 515-526), built from `stages` +
`waves` + `stageResultsById` after Execute completes.

```
{
  stages: [{
    id: string, name: string, inputContract: string, outputContract: string,
    dependsOn: string[],
    wave: number,          // 0-indexed wave this stage ran in
    modesUsed: string[]
  }],
  waves: string[][]        // waves[i] = array of stage ids that ran in parallel in wave i
}
```

Consumed by: `assets/reasoning-trace-viewer.html`'s `waveOf()` (lines
378-391) — the viewer recomputes wave numbers itself client-side from
`dependsOn`, it does NOT read the `wave` field; `wave`/`waves`/`modesUsed`
are included as forward-compatible extra data, currently unused by the
viewer's node rendering.

## Revise output

Producer: `solve-orchestrate.js`'s `REVISE_SCHEMA` (lines 447-457), one
agent dispatch applying `compass-draft-revise`'s methodology.

```
{
  scoreTable: [{criterion: string, score: number, requiredFix?: string}],  // score clamped [1,5] (c-task-1)
  revisedResult: string,   // composed result, revised per Step 3 (only at/below threshold), or unchanged
  changes: string[]        // one bullet per required fix actually applied; [] if nothing scored at/below threshold
}
```

Note: `score` is clamped to `[1, 5]` by `solve-orchestrate.js` before
being returned (added in `c-task-1`, commit `0455f53`) — the raw agent
response is not returned unclamped.
