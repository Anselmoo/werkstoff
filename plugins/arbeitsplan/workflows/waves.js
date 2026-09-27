export const meta = {
  name: 'arbeitsplan-waves',
  description: 'Execute a compiled multi-wave design table: parallel disjoint rows per wave, merge and gate between waves, resumable.',
  whenToUse:
    'Installed into a project by install_waves.py and launched by arbeitsplan-waves (or by hand) from the ' +
    'PRIMARY checkout with args {plan, state}: the compiled design (.claude/workflows/<name>.plan.json) and ' +
    'the state helper\'s state (<name>_state.py show). Runs the pre-wave nodes, every wave not yet done, then ' +
    'the post-wave nodes; stops at the first red gate, at a pending human gate, or on a contract breach, ' +
    'returning the state to resume from. Needs no werkstoff at runtime.',
  phases: [
    { title: 'Preflight', detail: 'script nodes before the waves: primary checkout only, clean tree' },
    { title: 'Build', detail: 'one worktree per row (a swarm row: N candidates and a blind referee)' },
    { title: 'Merge and gate', detail: 'merge the stage into the integration branch; gate and move the target on the last stage' },
    { title: 'After the waves', detail: 'smoke in a scratch directory, review, one fix round' },
  ],
}

// #90: a user request relayed into a subagent was addressed to the orchestrating
// session. The text is checked verbatim by scripts/ci/check_workflow_models.py --
// never paraphrase it.
const RELAYED = 'A user request about merging, pushing, committing, or releasing is addressed to the orchestrating session, not to you. Note it in your result and continue with your assigned scope; never act on it and never stop to debate it.'

// design_spec.py's vocabulary, restated: a Workflow script cannot import Python.
const MODEL_ALIASES = ['haiku', 'sonnet', 'opus', 'fable']
const MODEL_ID = /^claude-[a-z0-9]+(?:[-.][a-z0-9]+)*(?:\[1m\])?$/
const modelOk = (m) => typeof m === 'string' && (MODEL_ALIASES.includes(m) || MODEL_ID.test(m))
// What a {placeholder} may expand to -- the same class the project guard lets a
// template slot match, so a value the guard would deny is refused here first.
const SAFE = /^[A-Za-z0-9._/,=:@+-]+$/

const scriptSchema = (outputSchema) => ({
  type: 'object',
  additionalProperties: false,
  required: ['exit', 'stdout_digest', 'parsed'],
  properties: { exit: { type: 'integer' }, stdout_digest: { type: 'string' }, parsed: outputSchema },
})
const RECORD_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['recorded', 'row', 'head'],
  properties: { recorded: { type: 'boolean' }, row: { type: 'string' }, head: { type: 'string' } },
}
const REFEREE_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['winner', 'perCandidate'],
  properties: {
    winner: { type: ['string', 'null'] },
    perCandidate: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['branch', 'allPassed', 'failing'],
        properties: { branch: { type: 'string' }, allPassed: { type: 'boolean' }, failing: { type: 'array', items: { type: 'string' } } },
      },
    },
  },
}

// A strict JSON Schema check over the subset a design may declare. Returns the
// problems; [] is valid. The runtime enforces `schema` too, but a null result or
// a stubbed agent() bypasses that, and a contract nobody re-checks is prose.
function strictProblems(schema, value, where = 'output') {
  if (!schema || typeof schema !== 'object') return [`${where}: no schema to validate against`]
  const types = Array.isArray(schema.type) ? schema.type : schema.type ? [schema.type] : []
  const typeOf = (v) => (v === null ? 'null' : Array.isArray(v) ? 'array' : Number.isInteger(v) ? 'integer' : typeof v)
  const t = typeOf(value)
  if (types.length && !types.some((x) => x === t || (x === 'number' && t === 'integer'))) {
    return [`${where}: expected ${types.join('|')}, got ${t}`]
  }
  if (Array.isArray(schema.enum) && !schema.enum.includes(value)) return [`${where}: not one of the enum values`]
  const out = []
  if (t === 'object') {
    const props = schema.properties || {}
    for (const k of schema.required || []) if (!(k in value)) out.push(`${where}.${k}: required, missing`)
    for (const [k, v] of Object.entries(value)) {
      if (k in props) out.push(...strictProblems(props[k], v, `${where}.${k}`))
      else if (schema.additionalProperties === false) out.push(`${where}.${k}: not declared`)
    }
  }
  if (t === 'array' && schema.items) {
    value.forEach((v, j) => {
      out.push(...strictProblems(schema.items, v, `${where}[${j}]`))
    })
  }
  return out
}

function normalizeArgs(raw) {
  if (typeof raw === 'string') {
    // #106 comment item 1: state passed as a JSON string is the fragility this
    // interpreter exists to remove. Refuse it rather than parse it.
    throw new Error('arbeitsplan-waves: args arrived as a string. Pass {plan, state} as objects in the tool call, never JSON.stringify(...).')
  }
  if (!raw || typeof raw !== 'object' || !raw.plan || typeof raw.plan !== 'object' || !Array.isArray(raw.plan.nodes)) {
    throw new Error('arbeitsplan-waves: args.plan must be the parsed <name>.plan.json -- the Workflow tool has no filesystem, so the caller reads it and passes it verbatim.')
  }
  const state = raw.state && typeof raw.state === 'object' ? raw.state : {}
  return {
    plan: raw.plan,
    state: { waves: state.waves || {}, builders: state.builders || {}, approvals: state.approvals || {} },
  }
}

const opts = normalizeArgs(args)
const plan = opts.plan
const state = opts.state
if (plan.schemaVersion !== 'design/1') {
  return { error: `plan.schemaVersion ${JSON.stringify(plan.schemaVersion)} is not "design/1"; re-compile the design`, state }
}
const integ = plan.integration || {}
const runner = typeof plan.runnerAgent === 'string' && plan.runnerAgent ? plan.runnerAgent : null
if (!runner) return { error: 'plan.runnerAgent is missing -- install_waves.py writes it; a script node has no agent to run it', state }

const byId = Object.fromEntries(plan.nodes.map((n) => [n.id, n]))
const deps = (n) => n.depends_on || []
function ancestors(id) {
  const seen = new Set()
  const stack = [...deps(byId[id])]
  while (stack.length) {
    const d = stack.pop()
    if (seen.has(d) || !byId[d]) continue
    seen.add(d)
    stack.push(...deps(byId[d]))
  }
  return seen
}
// Kahn's order, ties broken by id: the same order design_spec.py validated.
function topo(ids) {
  const set = new Set(ids)
  const indeg = Object.fromEntries(ids.map((id) => [id, deps(byId[id]).filter((d) => set.has(d)).length]))
  const ready = ids.filter((id) => indeg[id] === 0).sort()
  const order = []
  while (ready.length) {
    const id = ready.shift()
    order.push(id)
    for (const m of ids) {
      if (deps(byId[m]).includes(id)) {
        indeg[m] -= 1
        if (indeg[m] === 0) { ready.push(m); ready.sort() }
      }
    }
  }
  return order
}

const events = []
const note = (kind, node, detail) => events.push({ kind, node, ...(detail || {}) })
let dispatched = 0
const ceiling = plan.budget && Number.isInteger(plan.budget.totalDispatches) ? plan.budget.totalDispatches : null
function spend(n, node) {
  // #106 R9: no cap by default -- subscription limits stop the run, and resume
  // makes that cheap. A design that declares a budget gets it enforced here.
  if (ceiling !== null && dispatched + n > ceiling) return `node ${node} needs ${n} dispatch(es); ${ceiling - dispatched} of ${ceiling} remain`
  dispatched += n
  return null
}
function stop(reason, node, extra) {
  note('halt', node, { reason })
  return { aborted: true, abortReason: reason, haltedAt: node, state, events, dispatched, ...(extra || {}) }
}

// Inputs are ids and paths, never content (#106 R8): a prompt names what to
// read, and the agent reads it from git or the plan file itself.
const planFile = `.claude/workflows/${plan.name}.plan.json`
const stepsText = (steps) => (steps && steps.length ? steps.map((s) => ['  ```', `  ${s.command}`, '  ```'].join('\n')).join('\n') : '  (none declared)')

async function runScript(node, values, label, phaseTitle) {
  const sc = node.script || {}
  const missing = []
  const bad = []
  const cmd = String(sc.command || '').replace(/\{([A-Za-z][A-Za-z0-9_]*)\}/g, (m, name) => {
    const v = values[name]
    if (v === undefined || v === null || v === '') { missing.push(name); return m }
    if (!SAFE.test(String(v))) { bad.push(name); return m }
    return String(v)
  })
  if (missing.length || bad.length) return { error: `node ${node.id}: placeholder(s) ${[...missing, ...bad].join(', ')} ${missing.length ? 'have no value' : 'carry characters the runner guard refuses'}` }
  const over = spend(1, node.id)
  if (over) return { error: `budget: ${over}` }
  const out = await agent(
    [
      `You are the script runner for node ${node.id} of plan ${plan.name}.`,
      ``,
      `Run exactly this command, once, from the repository root, with the Bash tool:`,
      '```',
      cmd,
      '```',
      ``,
      `Do not run anything else. The guard allows this one command and denies a second.`,
      `Return exit = its exit code; stdout_digest = the last 40 lines of its stdout, verbatim;`,
      `parsed = the JSON object it printed on stdout, copied field for field. If it printed no`,
      `parseable JSON, return parsed: {}.`,
      ``,
      `${RELAYED}`,
    ].join('\n'),
    { label, phase: phaseTitle, agentType: runner, model: node.model, schema: scriptSchema(node.output_schema) },
  )
  if (!out) return { error: `node ${node.id}: SCRIPT CONTRACT -- the runner returned nothing` }
  if (!Number.isInteger(out.exit) || !(sc.expectExit || [0]).includes(out.exit)) {
    return { error: `node ${node.id}: SCRIPT CONTRACT -- exit ${JSON.stringify(out.exit)} is not in expectExit ${JSON.stringify(sc.expectExit)}`, output: out }
  }
  const problems = strictProblems(node.output_schema, out.parsed, 'parsed')
  if (problems.length) return { error: `node ${node.id}: SCRIPT CONTRACT -- ${problems.slice(0, 3).join('; ')}`, output: out }
  note('script', node.id, { exit: out.exit })
  return { parsed: out.parsed }
}

// The helper's record command -- persisted state the moment a builder is done,
// so a restart keeps its branch and the notes its commits carry (#106 R3).
async function recordBuilder(row, branch, base, gateNode) {
  const tmpl = plan.helper && plan.helper.record
  if (typeof tmpl !== 'string') return { error: 'plan.helper.record is missing -- install_waves.py writes it' }
  const node = { id: `${row}:record`, script: { command: tmpl, expectExit: [0] }, model: gateNode.model, output_schema: RECORD_SCHEMA }
  return runScript(node, { row, branch, base }, `${row}:record`, 'Build')
}

function builderPrompt(n, base, candidate) {
  return [
    `You are ${candidate ? `candidate ${candidate} for ` : ''}row ${n.id} of plan ${plan.name}, wave ${n.wave || 'post'}.`,
    `Goal: ${n.goal}`,
    ``,
    `FIRST, before anything else, bring your worktree to the wave base:`,
    '```',
    `git merge --ff-only ${base}`,
    '```',
    `If that fails, stop and return baseSha = the output of \`git rev-parse HEAD\`; the run halts on a wrong base rather than building on one.`,
    ``,
    `You own exactly these paths (writeScope): ${JSON.stringify(n.writeScope || [])}. Touch nothing else;`,
    `a shared file you need is some other row's or the integrator's, never yours.`,
    `Setup steps, in order:`,
    stepsText(n.setup),
    `Acceptance, each must exit 0 before you finish:`,
    stepsText(n.acceptance),
    ``,
    `Inputs, by id or path only -- read what you need from git or from ${planFile}: ${JSON.stringify(n.inputs || [])}.`,
    `Commit your work on your branch. Put your notes for later rows in the commit message body;`,
    `they are recorded from there and survive a restart.`,
    `Return branch = your branch name, baseSha = the commit you started from after the merge above, notes = your notes.`,
    ``,
    `${RELAYED}`,
  ].join('\n')
}

async function build(n, base) {
  const swarm = Number.isInteger(n.swarm) && n.swarm > 1 ? n.swarm : 1
  const over = spend(swarm + (swarm > 1 ? 1 : 0), n.id)
  if (over) return { error: `budget: ${over}` }
  // #106 R7: N candidates from the SAME prompt; nothing but the candidate id differs.
  const labels = Array.from({ length: swarm }, (_, k) => (swarm > 1 ? `${n.id}:c${k + 1}` : n.id))
  const results = await parallel(labels.map((label, k) => () => agent(
    builderPrompt(n, base, swarm > 1 ? `c${k + 1}` : null),
    { label, phase: 'Build', agentType: n.agentType, model: n.model, isolation: 'worktree', schema: n.output_schema },
  )))
  const valid = []
  for (let k = 0; k < results.length; k++) {
    const r = results[k]
    if (!r) continue
    const probs = strictProblems(n.output_schema, r, labels[k])
    if (probs.length) return { error: `row ${n.id}: output breaks its schema: ${probs.slice(0, 3).join('; ')}` }
    // #106 R1: the base is checked in code, not trusted from the prompt.
    if (r.baseSha !== base) return { error: `row ${labels[k]}: WRONG BASE -- started from ${r.baseSha}, the wave base is ${base}. Launch from the primary checkout.` }
    if (!SAFE.test(String(r.branch))) return { error: `row ${labels[k]}: branch ${JSON.stringify(r.branch)} is not a plain branch name` }
    valid.push(r)
  }
  if (!valid.length) return { error: `row ${n.id}: no builder returned a result` }
  if (swarm === 1) return { result: valid[0], losers: [] }
  // Blind referee (#106 R7): branch names and the row's acceptance commands --
  // no goal, no notes, no rationale, nothing a candidate wrote about itself.
  const branches = valid.map((r) => r.branch)
  const verdict = await agent(
    [
      `You are the blind referee for row ${n.id}. Candidates, by branch name only: ${branches.join(', ')}.`,
      `For each branch: check it out in your own worktree and run every acceptance command below.`,
      stepsText(n.acceptance),
      `winner = the branch on which every command exits 0 (ties: the first in the list above); null if none.`,
      `You judge the commands' exit codes, never the code's style or a commit message.`,
      ``,
      `${RELAYED}`,
    ].join('\n'),
    { label: `${n.id}:referee`, phase: 'Build', agentType: n.referee.agentType, model: n.referee.model, isolation: 'worktree', schema: REFEREE_SCHEMA },
  )
  if (!verdict || !verdict.winner || !branches.includes(verdict.winner)) {
    return { error: `row ${n.id}: NO CANDIDATE ACCEPTED -- the referee found no branch passing every acceptance command`, losers: branches }
  }
  // The loser is discarded, never merged.
  return { result: valid.find((r) => r.branch === verdict.winner), losers: branches.filter((b) => b !== verdict.winner) }
}

// ---- pre-wave nodes -----------------------------------------------------------
const waveNodes = plan.nodes.filter((n) => Number.isInteger(n.wave))
const waveCount = waveNodes.length ? Math.max(...waveNodes.map((n) => n.wave)) : 0
const waveAncestorOf = (id) => [...ancestors(id)].some((a) => Number.isInteger(byId[a].wave))
const outside = plan.nodes.filter((n) => !Number.isInteger(n.wave))
const pre = topo(outside.filter((n) => !waveAncestorOf(n.id)).map((n) => n.id))
const post = topo(outside.filter((n) => waveAncestorOf(n.id)).map((n) => n.id))
const results = {}
const values = { name: plan.name, runId: plan.runId, integration: integ.branch, target: integ.target }

// A human gate is BETWEEN runs: the run stops before the first node after an
// unapproved one and returns; `<name>_state.py approve --gate <id>` records the
// approval, and the next launch passes it in `state`.
function pendingGate(id) {
  return [...ancestors(id)].find((a) => byId[a].kind === 'human-gate' && !state.approvals[a]) || null
}

phase('Preflight')
for (const id of pre) {
  const n = byId[id]
  if (n.kind === 'human-gate') continue
  const gate = pendingGate(id)
  if (gate) return { pending_human_gate: gate, state, events, dispatched }
  if (!modelOk(n.model)) return stop(`node ${id} has no valid model; an inherited model defeats tiering`, id)
  if (n.kind !== 'script') return stop(`node ${id}: only script nodes may run before the waves in this interpreter`, id)
  const r = await runScript(n, values, id, 'Preflight')
  if (r.error) return stop(r.error, id, r.output ? { output: r.output } : null)
  results[id] = r.parsed
}
const pf = results[integ.preflight]
if (!pf) return stop(`integration.preflight ${JSON.stringify(integ.preflight)} did not run before the waves`, integ.preflight)
// #106 R1: agent worktrees branch from the PRIMARY checkout's HEAD. From a
// linked worktree every builder would start from the wrong base.
if (pf.linkedWorktree) return stop('PRIMARY CHECKOUT ONLY -- this run was launched from a linked worktree, and agent worktrees would branch from the primary checkout\'s HEAD instead. Relaunch from the primary checkout.', integ.preflight)
if (pf.dirty) return stop('the primary checkout has tracked changes; the merge-gate switches branches there. Commit or stash them first.', integ.preflight)

// ---- waves --------------------------------------------------------------------
let base = pf.head
for (let w = 1; w <= waveCount; w++) {
  const done = state.waves[String(w)]
  // #106 R3: a finished wave is skipped BEFORE any of its builders is dispatched
  // -- the hand-written prototype checked after, and re-ran a finished wave.
  if (done && done.status === 'done') {
    base = done.integrationSha
    note('wave-skipped', `wave ${w}`, { integrationSha: base })
    continue
  }
  const gateNode = waveNodes.find((n) => n.wave === w && n.kind === 'merge-gate')
  const rows = waveNodes.filter((n) => n.wave === w && n.kind === 'agent').map((n) => n.id)
  // Stages: rows that depend on no other row of their wave run first, in
  // parallel; an integrator that depends on them runs on their merged result.
  const level = {}
  for (const id of topo(rows)) level[id] = Math.max(0, ...deps(byId[id]).filter((d) => rows.includes(d)).map((d) => level[d] + 1))
  const stages = Math.max(...Object.values(level)) + 1
  let stageBase = base
  for (let s = 0; s < stages; s++) {
    const stageRows = rows.filter((id) => level[id] === s)
    for (const id of stageRows) {
      const gate = pendingGate(id)
      if (gate) return { pending_human_gate: gate, state, events, dispatched }
      if (!modelOk(byId[id].model)) return stop(`row ${id} has no valid model; an inherited model defeats tiering`, id)
    }
    phase('Build')
    const todo = stageRows.filter((id) => !(state.builders[id] && state.builders[id].base === stageBase))
    for (const id of stageRows.filter((x) => !todo.includes(x))) note('builder-skipped', id, { branch: state.builders[id].branch })
    const built = await parallel(todo.map((id) => () => build(byId[id], stageBase)))
    const losers = []
    for (let k = 0; k < todo.length; k++) {
      const b = built[k] || { error: `row ${todo[k]}: the builder dispatch failed` }
      if (b.losers) losers.push(...b.losers)
      if (b.error) return stop(b.error, todo[k], { discard: losers })
      const rec = await recordBuilder(todo[k], b.result.branch, stageBase, gateNode)
      if (rec.error) return stop(rec.error, todo[k])
      state.builders[todo[k]] = { branch: b.result.branch, base: stageBase, notes: b.result.notes || [] }
    }
    phase('Merge and gate')
    const final = s === stages - 1
    const branches = stageRows.map((id) => `${id}=${state.builders[id].branch}`).join(',')
    const r = await runScript(gateNode, { ...values, wave: w, stage: s, final: final ? 1 : 0, branches, discard: losers.length ? losers.join(',') : 'none', base: stageBase }, `${gateNode.id}:s${s}`, 'Merge and gate')
    if (r.error) return stop(r.error, gateNode.id, r.output ? { output: r.output } : null)
    const g = r.parsed
    results[gateNode.id] = g
    if (!g.green) {
      // #106 R4/R5: the target never moved; every worktree is kept and named,
      // and each finding says whether only the primary checkout produced it.
      return stop(`wave ${w} gate is RED; ${integ.target} was not moved`, gateNode.id, { findings: g.findings, kept: g.kept })
    }
    if (final && !g.targetMoved) return stop(`wave ${w} gate is green but ${integ.target} did not move; refusing to start wave ${w + 1} on an unmoved base`, gateNode.id)
    stageBase = g.integrationSha
  }
  state.waves[String(w)] = { status: 'done', integrationSha: stageBase }
  base = stageBase
}

// ---- post-wave nodes ----------------------------------------------------------
for (const id of post) {
  const n = byId[id]
  if (n.kind === 'human-gate') continue
  const gate = pendingGate(id)
  if (gate) return { pending_human_gate: gate, state, events, dispatched }
  if (n.when && (results[n.when.node] || {})[n.when.field] !== n.when.equals) {
    note('skipped-by-condition', id, { when: n.when })
    continue
  }
  if (!modelOk(n.model)) return stop(`node ${id} has no valid model; an inherited model defeats tiering`, id)
  phase('After the waves')
  if (n.kind === 'script') {
    const r = await runScript(n, { ...values, base }, id, 'After the waves')
    if (r.error) return stop(r.error, id, r.output ? { output: r.output } : null)
    results[id] = r.parsed
    continue
  }
  const over = spend(1, id)
  if (over) return stop(`budget: ${over}`, id)
  const where = n.where === 'scratch'
    ? [
        `Work in a NEW scratch directory OUTSIDE this repository (never inside it): export the`,
        `integration head ${base} there with \`git archive ${base}\` and run these steps in it, in order:`,
        stepsText(n.steps),
        n.skip ? `This node declares no steps: ${n.skip}. Report passed: true and say so.` : ``,
      ].join('\n')
    : n.where === 'worktree'
      ? [`FIRST, in your worktree, bring it to the integration head:`, '```', `git merge --ff-only ${base}`, '```',
          `Return baseSha = the commit you started from, branch = your branch, notes = what you changed.`,
          `You own exactly: ${JSON.stringify(n.writeScope || [])}.`].join('\n')
      : `Read the integration head ${base} (branch ${integ.branch}) in the primary checkout. Write nothing.`
  const out = await agent(
    [
      `You are node ${id} (${n.role || n.kind}) of plan ${plan.name}. Goal: ${n.goal}`,
      where,
      `Inputs, by id or path only -- read what you need from git or from ${planFile}: ${JSON.stringify(n.inputs || [])}.`,
      ``,
      `${RELAYED}`,
    ].join('\n'),
    { label: id, phase: 'After the waves', agentType: n.agentType, model: n.model, isolation: n.where === 'worktree' ? 'worktree' : undefined, schema: n.output_schema },
  )
  if (!out) return stop(`node ${id} returned nothing`, id)
  const probs = strictProblems(n.output_schema, out, id)
  if (probs.length) return stop(`node ${id}: output breaks its schema: ${probs.slice(0, 3).join('; ')}`, id)
  results[id] = out
  if (n.where === 'worktree') {
    if (out.baseSha !== base) return stop(`node ${id}: WRONG BASE -- started from ${out.baseSha}, expected ${base}`, id)
    // One fix round: its branch goes through the last wave's merge-gate again.
    const lastGate = waveNodes.find((m) => m.wave === waveCount && m.kind === 'merge-gate')
    const r = await runScript(lastGate, { ...values, wave: waveCount, stage: 'fix', final: 1, branches: `${id}=${out.branch}`, discard: 'none', base }, `${lastGate.id}:fix`, 'After the waves')
    if (r.error) return stop(r.error, lastGate.id, r.output ? { output: r.output } : null)
    if (!r.parsed.green) return stop(`the fix round's gate is RED; ${integ.target} was not moved`, lastGate.id, { findings: r.parsed.findings, kept: r.parsed.kept })
    base = r.parsed.integrationSha
  }
}

return { aborted: false, state, results, events, dispatched, integrationSha: base }
