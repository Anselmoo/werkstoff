export const meta = {
  name: 'compass-optimize-instruction',
  description: 'APE: exactly 5 framings drafted in parallel, scored on fixed test cases, winner critiqued',
  phases: [
    { title: 'Generate', detail: 'one candidate per APE framing, in parallel' },
    { title: 'Score', detail: 'each candidate against the exact provided test cases' },
    { title: 'Critique', detail: 'meta-prompting 4-item checklist on the winner only' },
  ],
}

// Numeric bounds / framing set as constants (spec requirement 2).
const APE_FRAMINGS = ['rule-based', 'example-based', 'definition-based', 'question-based', 'chain-of-thought-based']
const CANDIDATE_COUNT = APE_FRAMINGS.length // exactly 5
const CHECKLIST_SIZE = 4
const FRAMING_ORDER = Object.fromEntries(APE_FRAMINGS.map((f, i) => [f, i]))

const taskDesc = args?.taskDescription
const testCases = args?.testCases
if (!taskDesc) throw new Error('optimize-instruction: args.taskDescription is required')
if (!Array.isArray(testCases) || testCases.length < 3 || testCases.length > 5) {
  throw new Error('optimize-instruction: 3-5 real test cases {input, expectedOutcome} required')
}
for (const tc of testCases) {
  if (tc.input == null || tc.expectedOutcome == null) {
    throw new Error('optimize-instruction: every test case needs input and expectedOutcome')
  }
}

phase('Generate')
const CAND_SCHEMA = {
  type: 'object', required: ['framing', 'prompt'],
  properties: { framing: { type: 'string' }, prompt: { type: 'string' } },
}
// One candidate per framing, committed fully to that framing (no blending).
const candidates = (await parallel(APE_FRAMINGS.map((framing) => () =>
  agent(
    `Draft ONE candidate instruction for this recurring task using ONLY the "${framing}" APE framing. ` +
    `Commit fully to that framing — never blend in another framing's structure.\n\nTask:\n${taskDesc}`,
    { label: `gen:${framing}`, phase: 'Generate', agentType: 'compass:instruction-candidate', schema: CAND_SCHEMA },
  ),
))).filter(Boolean)

if (candidates.length !== CANDIDATE_COUNT) {
  throw new Error(`optimize-instruction: expected exactly ${CANDIDATE_COUNT} candidates, got ${candidates.length}`)
}
const framings = candidates.map((c) => c.framing).sort()
if (JSON.stringify(framings) !== JSON.stringify([...APE_FRAMINGS].sort())) {
  throw new Error('optimize-instruction: candidates must cover exactly the 5 APE framings')
}

phase('Score')
const SCORE_SCHEMA = {
  type: 'object', required: ['passed'],
  properties: { passed: { type: 'integer', minimum: 0, maximum: testCases.length } },
}
const scored = await parallel(candidates.map((c) => () =>
  agent(
    `Score this candidate instruction against the EXACT test cases below — do not invent, drop, ` +
    `or adjust any test case or expected outcome. Report how many of the ${testCases.length} it passes.\n\n` +
    `Candidate (${c.framing}):\n${c.prompt}\n\nTest cases:\n${JSON.stringify(testCases, null, 2)}`,
    { label: `score:${c.framing}`, phase: 'Score', agentType: 'compass:instruction-candidate', schema: SCORE_SCHEMA },
  ).then((s) => ({ ...c, score: s.passed })),
))

// Highest score; ties broken by framing precedence order.
scored.sort((a, b) => (b.score - a.score) || (FRAMING_ORDER[a.framing] - FRAMING_ORDER[b.framing]))
const winner = scored[0]
log(`Winner: ${winner.framing} (${winner.score}/${testCases.length})`)

phase('Critique')
const CRIT_SCHEMA = {
  type: 'object', required: ['checklist', 'final_prompt'],
  properties: {
    checklist: {
      type: 'array', minItems: CHECKLIST_SIZE, maxItems: CHECKLIST_SIZE,
      items: { type: 'object', required: ['criterion', 'pass'],
        properties: { criterion: { type: 'string' }, pass: { type: 'boolean' } } },
    },
    final_prompt: { type: 'string' },
  },
}
const critique = await agent(
  `Apply meta-prompting's ${CHECKLIST_SIZE}-item critique checklist to this WINNING candidate only ` +
  `(behavioral rules unambiguous? handles out-of-scope? output-format rules mutually compatible? ` +
  `no two-way-interpretable instruction?). Revise ONLY failing items; leave passing text untouched. ` +
  `Return the checklist and the final prompt.\n\nWinner (${winner.framing}):\n${winner.prompt}`,
  { label: 'critique:winner', phase: 'Critique', agentType: 'compass:instruction-candidate', schema: CRIT_SCHEMA },
)
if (critique.checklist.length !== CHECKLIST_SIZE) {
  throw new Error(`optimize-instruction: critique checklist must have exactly ${CHECKLIST_SIZE} items`)
}

return {
  candidates: scored.map((c) => ({ framing: c.framing, score: `${c.score}/${testCases.length}` })),
  winner: winner.framing,
  critique: critique.checklist,
  final_prompt: critique.final_prompt,
}
