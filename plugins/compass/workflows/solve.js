export const meta = {
  name: 'compass-solve',
  description: 'Clarify -> Explore (conditional) -> Decompose -> Execute (topological waves) -> Revise',
  phases: [
    { title: 'Clarify', detail: 'scope, flag uncertainties, pause if any block' },
    { title: 'Explore', detail: 'conditional: only if multiple viable approaches' },
    { title: 'Decompose', detail: '2-5 stages with validated acyclic dependsOn graph' },
    { title: 'Execute', detail: "Kahn's algorithm waves; stages in a wave run in parallel" },
    { title: 'Revise', detail: 'score 1-5 against criteria, revise at/below threshold' },
  ],
}

// --- Numeric bounds as constants in code (spec requirement 2) ---
const CLARIFY_FLAG_THRESHOLD = 70
const MIN_STAGES = 2
const MAX_STAGES = 5
const REVISE_MIN = 1
const REVISE_MAX = 5
const REVISE_THRESHOLD = 3
const MAX_REVISION_CYCLES = 2
const PHASE_ORDER = ['Clarify', 'Explore', 'Decompose', 'Execute', 'Revise']
const MODES = ['reason-verify', 'investigate-dynamically', 'ground-evidence', 'calibrate-format']

// Kahn's algorithm: returns topological waves AND detects cycles/dangling refs.
function computeWaves(stages) {
  if (!Array.isArray(stages) || stages.length < MIN_STAGES) {
    throw new Error(`decompose: need >= ${MIN_STAGES} stages (fewer means it did not need decomposing)`)
  }
  if (stages.length > MAX_STAGES) {
    throw new Error(`decompose: > ${MAX_STAGES} stages signals the task needs re-scoping`)
  }
  const ids = new Set()
  for (const s of stages) {
    if (!s.id || !s.input_contract || !s.output_contract || !Array.isArray(s.dependsOn)) {
      throw new Error(`decompose: stage ${s.id ?? '?'} missing id/contracts/dependsOn`)
    }
    if (ids.has(s.id)) throw new Error(`decompose: duplicate stage id ${s.id}`)
    ids.add(s.id)
  }
  for (const s of stages) {
    for (const d of s.dependsOn) {
      if (!ids.has(d)) throw new Error(`decompose: stage ${s.id} dependsOn non-existent ${d}`)
      if (d === s.id) throw new Error(`decompose: stage ${s.id} depends on itself`)
    }
  }
  const entries = stages.filter((s) => s.dependsOn.length === 0)
  if (entries.length === 0) throw new Error('decompose: no entry point (need one stage with dependsOn: [])')

  const done = new Set(); const waves = []; const remaining = new Set(stages.map((s) => s.id))
  const byId = Object.fromEntries(stages.map((s) => [s.id, s]))
  while (remaining.size) {
    const wave = [...remaining].filter((id) => byId[id].dependsOn.every((d) => done.has(d))).sort()
    if (wave.length === 0) throw new Error(`decompose: cycle detected among ${[...remaining].sort()}`)
    wave.forEach((id) => { remaining.delete(id); done.add(id) })
    waves.push(wave)
  }
  return waves
}

const rawTask = args?.task ?? args?.rawTask
if (!rawTask) throw new Error('compass-solve: args.task (the raw task) is required')
const phasesRun = []

// ---------- CLARIFY ----------
// Workflow scripts have no filesystem access, so this script cannot call
// `compass.py state-find` itself. When the calling SKILL.md already did that
// lookup (rule: solve-reuses-prior-standalone-run) and found a prior
// compass-clarify-scope run for this exact `rawTask`, it passes the result in
// as `args.priorClarify` — matching the CLARIFY_SCHEMA shape below — and this
// script reuses it instead of dispatching a fresh agent.
phase('Clarify')
phasesRun.push('Clarify')
const CLARIFY_SCHEMA = {
  type: 'object',
  required: ['scoped_task', 'flagged_uncertainties', 'success_criteria'],
  properties: {
    scoped_task: { type: 'string' },
    flagged_uncertainties: {
      type: 'array',
      items: {
        type: 'object', required: ['element', 'confidence', 'blocking'],
        properties: {
          element: { type: 'string' },
          confidence: { type: 'integer', minimum: 0, maximum: 100 },
          blocking: { type: 'boolean' },
          default_interpretation: { type: 'string' },
        },
      },
    },
    success_criteria: { type: 'array', items: { type: 'object' } },
  },
}
const clarify = args?.priorClarify ?? await agent(
  `Scope this task. Restate it with every default interpretation stated inline. List known facts ` +
  `(mark any below 90% confidence with the warning marker). For each uncertainty give ` +
  `{element, default_interpretation, confidence 0-100, blocking}. Any uncertainty with confidence ` +
  `below ${CLARIFY_FLAG_THRESHOLD} MUST be flagged. State success criteria.\n\nTask:\n${rawTask}`,
  { label: 'clarify', phase: 'Clarify', schema: CLARIFY_SCHEMA },
)
if (args?.priorClarify) log('Clarify: reusing a prior compass-clarify-scope run (args.priorClarify).')

// Enforce the flag gate and the blocking-pause in code.
const flagged = clarify.flagged_uncertainties.filter((u) => u.confidence < CLARIFY_FLAG_THRESHOLD)
const blocking = flagged.filter((u) => u.blocking === true)
if (blocking.length > 0) {
  // MUST pause and wait for user input — return early, do NOT proceed silently.
  return {
    status: 'PAUSED_AWAITING_USER',
    reason: 'blocking uncertainty after Clarify',
    scoped_task: clarify.scoped_task,
    blocking_uncertainties: blocking,
    next: 'Resolve each blocking uncertainty (compass-verify-assumptions), then re-run with answers.',
  }
}

// ---------- EXPLORE (conditional) ----------
// Same filesystem constraint as Clarify above: if the calling SKILL.md found a
// prior compass-explore-branches run matching clarify.scoped_task, it passes
// it in as `args.priorExplore` ({ selected, scores }) and this script reuses
// it instead of dispatching the explore-branches workflow again.
let explore = null
const hasStrategicFork = !!args?.multipleApproaches
if (hasStrategicFork) {
  phase('Explore')
  phasesRun.push('Explore')
  if (args?.priorExplore) {
    explore = args.priorExplore
    log(`Explore: reusing a prior compass-explore-branches run (args.priorExplore). Selected: ${explore.selected}`)
  } else {
    explore = await workflow('compass-explore-branches', { problem: clarify.scoped_task,
      requestedBranches: args?.requestedBranches, maxBranchCount: args?.maxBranchCount })
    log(`Explore selected: ${explore.selected}`)
  }
} else {
  log('Explore skipped: one obvious approach, no strategic fork.')
}

// ---------- DECOMPOSE ----------
phase('Decompose')
phasesRun.push('Decompose')
const DECOMPOSE_SCHEMA = {
  type: 'object', required: ['stages'],
  properties: {
    stages: {
      type: 'array', minItems: MIN_STAGES, maxItems: MAX_STAGES,
      items: {
        type: 'object', required: ['id', 'name', 'input_contract', 'output_contract', 'dependsOn'],
        properties: {
          id: { type: 'string' }, name: { type: 'string' },
          input_contract: { type: 'string' }, output_contract: { type: 'string' },
          dependsOn: { type: 'array', items: { type: 'string' } },
        },
      },
    },
  },
}
const approach = explore ? `Selected approach: ${explore.selected}` : clarify.scoped_task
const decomposed = await agent(
  `Break this into ${MIN_STAGES}-${MAX_STAGES} stages. Each stage: {id, name, input_contract, ` +
  `output_contract, dependsOn:[stage ids]}. At least one stage must have dependsOn: []. No cycles, ` +
  `no dangling references.\n\n${approach}\n\nScoped task:\n${clarify.scoped_task}`,
  { label: 'decompose', phase: 'Decompose', schema: DECOMPOSE_SCHEMA },
)
const waves = computeWaves(decomposed.stages) // throws on any graph violation
log(`DAG valid: ${decomposed.stages.length} stages in ${waves.length} wave(s)`)

// ---------- EXECUTE (topological waves) ----------
phase('Execute')
phasesRun.push('Execute')
const byId = Object.fromEntries(decomposed.stages.map((s) => [s.id, s]))
const results = {}
const STAGE_SCHEMA = {
  type: 'object', required: ['mode', 'output'],
  properties: { mode: { type: 'string', enum: MODES }, output: { type: 'string' } },
}
for (let w = 0; w < waves.length; w++) {
  // Stages within a wave run in parallel; waves run sequentially.
  const wave = waves[w]
  const waveOut = await parallel(wave.map((id) => () => {
    const s = byId[id]
    const upstream = s.dependsOn.map((d) => `${d} -> ${results[d]?.output ?? ''}`).join('\n')
    return agent(
      `Execute stage "${s.name}". FIRST decide your execution mode at runtime from this stage's ` +
      `content — one of: ${MODES.join(', ')} — then produce the output.\n\n` +
      `Input contract: ${s.input_contract}\nOutput contract: ${s.output_contract}\n` +
      (upstream ? `Upstream outputs:\n${upstream}\n` : ''),
      { label: `exec:${id} (wave ${w + 1})`, phase: 'Execute', schema: STAGE_SCHEMA },
    ).then((r) => ({ id, ...r }))
  }))
  for (const r of waveOut.filter(Boolean)) {
    if (!MODES.includes(r.mode)) throw new Error(`execute: stage ${r.id} returned invalid mode ${r.mode}`)
    results[r.id] = r
  }
}

// ---------- REVISE ----------
phase('Revise')
phasesRun.push('Revise')
const composed = Object.values(results).map((r) => `## ${byId[r.id].name} [${r.mode}]\n${r.output}`).join('\n\n')
const criteria = args?.successCriteria ?? clarify.success_criteria?.map((c) => c.criterion ?? c) ?? []
let revision = null
if (Array.isArray(criteria) && criteria.length >= 3) {
  const REVISE_SCHEMA = {
    type: 'object', required: ['scores', 'revised', 'changes'],
    properties: {
      scores: { type: 'array', items: { type: 'object', required: ['criterion', 'score'],
        properties: { criterion: { type: 'string' },
          score: { type: 'integer', minimum: REVISE_MIN, maximum: REVISE_MAX } } } },
      revised: { type: 'string' }, changes: { type: 'array', items: { type: 'string' } },
    },
  }
  let draft = composed
  for (let cycle = 1; cycle <= MAX_REVISION_CYCLES; cycle++) {
    revision = await agent(
      `Score this draft ${REVISE_MIN}-${REVISE_MAX} against EACH criterion independently. Revise ONLY ` +
      `criteria scoring at or below ${REVISE_THRESHOLD}; leave above-threshold text untouched. Report ` +
      `one change bullet per fix.\n\nCriteria:\n${JSON.stringify(criteria)}\n\nDraft:\n${draft}`,
      { label: `revise:cycle-${cycle}`, phase: 'Revise', schema: REVISE_SCHEMA },
    )
    const failing = revision.scores.filter((s) => s.score <= REVISE_THRESHOLD)
    if (failing.length > 0 && revision.changes.length === 0) {
      throw new Error('revise: revision presented without a changes list')
    }
    draft = revision.revised
    if (failing.length === 0) break // converged; no second cycle needed
    if (cycle === MAX_REVISION_CYCLES) log(`revise: still failing after ${MAX_REVISION_CYCLES} cycles`)
  }
}

// Final phase-order assertion in code.
const canonical = PHASE_ORDER.filter((p) => phasesRun.includes(p))
if (JSON.stringify(phasesRun) !== JSON.stringify(canonical)) {
  throw new Error(`solve: phases ran out of order: ${phasesRun}`)
}

return {
  status: 'COMPLETE',
  scoped_task: clarify.scoped_task,
  explore: explore ? { selected: explore.selected, scores: explore.scores } : null,
  stage_plan: decomposed.stages.map((s) => ({ id: s.id, name: s.name, dependsOn: s.dependsOn })),
  waves,
  composed_result: composed,
  revised: revision ? { scores: revision.scores, changes: revision.changes, result: revision.revised } : null,
  phases_run: phasesRun,
}
