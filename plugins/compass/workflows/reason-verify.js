export const meta = {
  name: 'compass-reason-verify',
  description: 'Self-consistency (Rung 2a): exactly 3 isolated reasoning-path attempts, then majority vote',
  phases: [
    { title: 'Attempt', detail: 'three isolated strategies run in parallel' },
    { title: 'Reconcile', detail: 'majority answer across the three attempts' },
  ],
}

// Numeric bounds as constants (spec requirement 2).
const SELF_CONSISTENCY_ATTEMPTS = 3
const STRATEGIES = ['forward deduction', 'backward from options', 'constraint mapping']

const task = args?.task
if (!task) throw new Error('reason-verify: args.task is required')
if (STRATEGIES.length !== SELF_CONSISTENCY_ATTEMPTS) {
  throw new Error('reason-verify: strategy count must equal SELF_CONSISTENCY_ATTEMPTS')
}

const multimodal = !!args?.hasImageOrDiagram
if (multimodal) log('Input contains an image/diagram: Multimodal-CoT applied before reasoning.')

phase('Attempt')
const ATTEMPT_SCHEMA = {
  type: 'object',
  required: ['strategy', 'answer', 'reasoning'],
  properties: {
    strategy: { type: 'string' },
    answer: { type: 'string' },
    reasoning: { type: 'string' },
  },
}
// Each attempt is a separate, isolated dispatch. No attempt can see the others.
const attempts = (await parallel(STRATEGIES.map((strategy) => () =>
  agent(
    (multimodal ? 'Apply Multimodal-CoT (describe the visual, then reason) FIRST.\n\n' : '') +
    `Solve this task using ONLY the "${strategy}" strategy, in complete isolation. ` +
    `You cannot see any other attempt; do not reference or simulate one.\n\n` +
    `Task:\n${task}\n\nReturn your strategy name, your final answer, and your reasoning.`,
    { label: `attempt:${strategy}`, phase: 'Attempt', agentType: 'compass:reasoning-path', schema: ATTEMPT_SCHEMA },
  ),
))).filter(Boolean)

// Enforce exactly 3 independent attempts covering all three strategies.
if (attempts.length !== SELF_CONSISTENCY_ATTEMPTS) {
  throw new Error(`reason-verify: expected exactly ${SELF_CONSISTENCY_ATTEMPTS} attempts, got ${attempts.length}`)
}
const seen = new Set(attempts.map((a) => a.strategy))
for (const s of STRATEGIES) {
  if (!seen.has(s)) throw new Error(`reason-verify: missing required strategy "${s}"`)
}

phase('Reconcile')
const tally = {}
for (const a of attempts) tally[a.answer] = (tally[a.answer] || 0) + 1
const [best] = Object.entries(tally).sort((x, y) => y[1] - x[1])
log(`Vote: ${JSON.stringify(tally)}`)

return {
  multimodal_cot_applied: multimodal,
  attempts,
  final_answer: best[0],
  agreement: `${best[1]}/${SELF_CONSISTENCY_ATTEMPTS}`,
}
