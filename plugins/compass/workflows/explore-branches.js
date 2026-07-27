export const meta = {
  name: 'compass-explore-branches',
  description: 'Propose N approaches in parallel (no anchoring), score each independently, select the winner',
  phases: [
    { title: 'Propose', detail: 'one branch-proposer per angle, dispatched in parallel' },
    { title: 'Score', detail: 'each branch scored in a separate, comparison-free dispatch' },
    { title: 'Select', detail: 'highest total; ties broken by lower risk' },
  ],
}

// --- Numeric bounds as constants in code (spec requirement 2) ---
const DEFAULT_BRANCHES = 3
const HARD_MAX_BRANCHES = 6
const SCORE_MIN = 1
const SCORE_MAX = 10
const AXES = ['feasibility', 'impact', 'risk']
// Distinct angles; each proposer commits fully to its own (anti-anchoring).
const ANGLES = ['conservative', 'ambitious', 'pragmatic', 'contrarian', 'minimal', 'maximal']

function effectiveCap(requested, configMax) {
  let cap = HARD_MAX_BRANCHES
  if (configMax != null) cap = Math.min(cap, configMax)
  if (requested == null) return Math.min(DEFAULT_BRANCHES, cap)
  return Math.min(requested, cap)
}

function requireScore(v, where) {
  if (typeof v !== 'number' || !Number.isInteger(v) || v < SCORE_MIN || v > SCORE_MAX) {
    throw new Error(`${where}: score ${v} outside [${SCORE_MIN},${SCORE_MAX}]`)
  }
  return v
}

const problem = args?.problem ?? args?.scopedTask
if (!problem) throw new Error('explore-branches: args.problem (scoped problem statement) is required')

const count = effectiveCap(args?.requestedBranches ?? null, args?.maxBranchCount ?? null)
const angles = ANGLES.slice(0, count)
log(`Proposing ${count} branches (cap=${count}) under angles: ${angles.join(', ')}`)

// PROPOSE — parallel, independent. No proposer sees another's output: anchoring
// is prevented structurally, not by instruction.
phase('Propose')
const BRANCH_SCHEMA = {
  type: 'object',
  required: ['name', 'description'],
  properties: { name: { type: 'string' }, description: { type: 'string' } },
}
const branches = (await parallel(angles.map((angle) => () =>
  agent(
    `You are proposing ONE approach to this scoped problem under the assigned angle "${angle}".\n\n` +
    `Problem:\n${problem}\n\n` +
    `Commit fully to the "${angle}" angle as a hard constraint. Do NOT soften it toward a ` +
    `safe middle ground — its job is to force the branch set apart. Return only your one branch.`,
    { label: `propose:${angle}`, phase: 'Propose', agentType: 'compass:branch-proposer', schema: BRANCH_SCHEMA },
  ),
))).filter(Boolean)

if (branches.length < 2) throw new Error('explore-branches: need >= 2 distinct branches to compare')

// SCORE — each branch scored in isolation (proposer never scores its own branch,
// scorer never compares against siblings).
phase('Score')
const SCORE_SCHEMA = {
  type: 'object',
  required: ['feasibility', 'impact', 'risk', 'biggest_blocker'],
  properties: {
    feasibility: { type: 'integer', minimum: SCORE_MIN, maximum: SCORE_MAX },
    impact: { type: 'integer', minimum: SCORE_MIN, maximum: SCORE_MAX },
    risk: { type: 'integer', minimum: SCORE_MIN, maximum: SCORE_MAX },
    biggest_blocker: { type: 'string' },
  },
}
const scored = (await parallel(branches.map((b) => () =>
  agent(
    `Score exactly ONE branch on Feasibility, Impact, and Risk, each ${SCORE_MIN}-${SCORE_MAX}. ` +
    `Do NOT compare it against any other branch — score it on its own merits — and name its biggest blocker.\n\n` +
    `Branch "${b.name}": ${b.description}`,
    { label: `score:${b.name}`, phase: 'Score', agentType: 'compass:branch-proposer', schema: SCORE_SCHEMA },
  ).then((s) => ({ name: b.name, description: b.description, ...s })),
))).filter(Boolean)

// SELECT — Total = raw sum (Risk NOT inverted). Highest total; tie -> lower risk.
phase('Select')
for (const s of scored) {
  for (const axis of AXES) requireScore(s[axis], `${s.name}.${axis}`)
  s.total = s.feasibility + s.impact + s.risk
}
scored.sort((a, b) => (b.total - a.total) || (a.risk - b.risk))
const winner = scored[0]
log(`Selected "${winner.name}" (total ${winner.total}, risk ${winner.risk})`)

return {
  branches: branches.map((b) => ({ name: b.name, description: b.description })),
  scores: scored.map((s) => ({
    branch: s.name, Feasibility: s.feasibility, Impact: s.impact, Risk: s.risk,
    Total: s.total, biggest_blocker: s.biggest_blocker,
  })),
  selected: winner.name,
  rationale: `Highest total (${winner.total}); ties broken by lowest risk.`,
}
