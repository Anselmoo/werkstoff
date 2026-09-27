#!/usr/bin/env node
// Executes workflows/waves.js against stub agent()/parallel()/phase() hooks.
//
// usage: node plugins/arbeitsplan/scripts/test_waves_workflow.js
//
// No tokens, no Workflow tool, no git: waves.js is evaluated exactly as the
// runtime evaluates it (meta's export stripped, the body compiled as an async
// function) against the committed Go design fixture, and every agent() answers
// by label. Each case is one of #106's recorded failures, asserted rather than
// described. Then it sabotages itself: each SABOTAGE plants one defect into
// waves.js in memory and the suite must go red, or the case that should catch
// it is not catching anything.
//
// Exit: 0 every case passed and every sabotage was caught, 1 otherwise.
'use strict'

const fs = require('node:fs')
const path = require('node:path')

const ROOT = path.resolve(__dirname, '..')
const SRC = fs.readFileSync(path.join(ROOT, 'workflows', 'waves.js'), 'utf8')
const DESIGN = JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures', 'design', 'waves.design.json'), 'utf8'))
const RUST = JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures', 'design', 'integrator.design.json'), 'utf8'))
const AUTHORED = JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures', 'design', 'authored.design.json'), 'utf8'))
const AsyncFunction = Object.getPrototypeOf(async () => {}).constructor
const BODY = SRC.replace(/^export\s+(?=const\s+meta\b)/m, '')
let body = BODY
let quiet = false

const clone = (o) => JSON.parse(JSON.stringify(o))
// What install_waves.py adds to a design to make it a plan.
const planOf = (design) => {
  const plan = {
    ...clone(design),
    runnerAgent: `${design.name}-runner`,
    helper: { record: `python3 .claude/workflows/${design.name}_state.py record --row {row} --branch {branch} --base {base}` },
  }
  if (design.nodes.some((n) => n.script && n.script.author)) {
    plan.authorAgent = `${design.name}-author`
    plan.helper.verify = `python3 .claude/workflows/${design.name}_state.py verify-step --node {node}`
  }
  return plan
}
const STEP_FILE = '.claude/workflows/rebuild-cli.steps/api-surface.py'
const PLAN = planOf(DESIGN)

async function execute(args, answer) {
  const calls = []
  const agent = async (prompt, opts) => {
    calls.push({ label: opts.label, opts, prompt })
    return answer(opts.label, prompt, opts)
  }
  const parallel = async (thunks) => Promise.all(thunks.map((t) => t().catch(() => null)))
  const fn = new AsyncFunction('args', 'agent', 'parallel', 'pipeline', 'phase', 'log', 'budget', body)
  let result
  let threw = null
  try {
    result = await fn(args, agent, parallel, null, () => {}, () => {}, { total: null })
  } catch (e) {
    threw = e
  }
  return { result, calls, threw }
}

const script = (parsed, exit = 0) => ({ exit, stdout_digest: 'tail', parsed })
const baseOf = (prompt) => (prompt.match(/git merge --ff-only (\S+)/) || [])[1]
const cmdOf = (prompt) => prompt.split('```')[1].trim()

// The happy answers. Overridable per case.
function happy(label, prompt) {
  if (label === 'preflight') return script({ linkedWorktree: false, dirty: false, head: 'H0', python: '3.12.1' })
  if (label.endsWith(':record')) return script({ recorded: true, row: label.split(':')[0], head: 'x' })
  if (/^gate-\d+:/.test(label)) {
    const cmd = cmdOf(prompt)
    const final = / --final 1 /.test(`${cmd} `)
    const tag = label.replace(/[^A-Za-z0-9]/g, '')
    return script({ green: true, integrationSha: `I-${tag}`, targetMoved: final, findings: [], kept: [] })
  }
  if (label === 'smoke') return { passed: true, scratchDir: '/tmp/scratch-1', failedStep: null }
  if (/^api-surface:author/.test(label)) return { path: STEP_FILE, notes: 'lists exported names' }
  if (/^api-surface:verify/.test(label)) return script({ verified: true, node: 'api-surface', path: STEP_FILE, problem: '' })
  if (label === 'api-surface') return script({ package: 'cmd/tool', exported: ['Run'] })
  if (label === 'review') return { blocking: false, findings: [] }
  if (label.endsWith(':referee')) return null
  // builders (and the fixer): echo the base the prompt told them to merge to
  const row = label.split(':')[0]
  const cand = label.includes(':c') ? `-${label.split(':')[1]}` : ''
  return { branch: `agent/${row}${cand}`, baseSha: baseOf(prompt), notes: [`done ${row}`] }
}

let failures = []
let count = 0
function ok(name, cond, detail) {
  count += 1
  if (!quiet) console.log(`  ${cond ? 'ok  ' : 'FAIL'} ${name}`)
  if (!cond) {
    failures.push(name)
    if (!quiet && detail !== undefined) console.log(`       ${JSON.stringify(detail).slice(0, 300)}`)
  }
}

// Every object level of every schema handed to agent() is strict, and no string
// field is JSON-in-a-string (#106 comment item 1).
function strictSchema(s) {
  if (!s || typeof s !== 'object') return true
  if (s.type === 'object' || s.properties) {
    if (s.additionalProperties !== false) return false
    for (const [k, v] of Object.entries(s.properties || {})) {
      if (v && v.type === 'string' && /json$/i.test(k)) return false
      if (!strictSchema(v)) return false
    }
  }
  if (s.items && !strictSchema(s.items)) return false
  return true
}

const SABOTAGE = [
  ['finished wave re-run', "if (done && done.status === 'done') {", 'if (false) {'],
  ['finished builder re-dispatched', 'const todo = stageRows.filter((id) => !(state.builders[id] && state.builders[id].base === stageBase))', 'const todo = stageRows'],
  ['base never checked', 'if (r.baseSha !== base) return', 'if (false) return'],
  ['linked worktree accepted', 'if (pf.linkedWorktree) return', 'if (false) return'],
  ['loser merged', 'return { result: valid.find((r) => r.branch === verdict.winner), losers: branches.filter((b) => b !== verdict.winner) }',
    'return { result: valid[valid.length - 1], losers: [] }'],
  ['red gate ignored', 'if (!g.green) {', 'if (false) {'],
  ['unsafe placeholder passed through', 'if (!SAFE.test(String(v))) { bad.push(name); return m }', ''],
  ['state accepted as a JSON string', "if (typeof raw === 'string') {", 'if (false) {'],
  ['human gate ignored', "return [...ancestors(id)].find((a) => byId[a].kind === 'human-gate' && !state.approvals[a]) || null", 'return null'],
  ['smoke placed in the repository', "const where = n.where === 'scratch'", "const where = false"],
  ['verified step re-authored', "if (status === 'verified') {", 'if (false) {'],
  ['refused step accepted', "problem: v.parsed.verified ? null : (v.parsed.problem || 'verify-step refused it without a reason')", 'problem: null'],
  ['author path unchecked', 'if (w.path !== stepPath(n)) return { id, problem', 'if (false) return { id, problem'],
  ['verifies run concurrently', 'const run = queue.then(fn)', 'const run = fn()'],
  ['effort dropped from the builder dispatch', "model: n.model, effort: n.effort, isolation: 'worktree'", "model: n.model, isolation: 'worktree'"],
  ['retry without the refusal', 'refused ? `Your previous version of this file was refused: ${refused}\\nFix exactly that.` : ``', '``'],
  ['authored step run before it is verified', "if (authored.length) {", 'if (false) {'],
]

async function suite() {
  // 1. Fresh run, end to end.
  {
    const { result, calls } = await execute({ plan: clone(PLAN), state: {} }, happy)
    const labels = calls.map((c) => c.label)
    ok('fresh: completes', result && !result.aborted, result)
    ok('fresh: preflight first', labels[0] === 'preflight', labels)
    ok('fresh: wave 1 rows before gate-1, wave 2 row after it',
      labels.indexOf('w1-parse') < labels.indexOf('gate-1:s0') && labels.indexOf('gate-1:s0') < labels.indexOf('w2-cli'), labels)
    ok('fresh: wave 2 builds from wave 1\'s integration sha, not the preflight head',
      baseOf(calls.find((c) => c.label === 'w2-cli').prompt) === 'I-gate1s0', calls.find((c) => c.label === 'w2-cli').prompt)
    ok('fresh: every builder is recorded as soon as it returns', ['w1-parse', 'w1-render', 'w2-cli'].every((r) => labels.includes(`${r}:record`)), labels)
    ok('fresh: builders run in worktree isolation', calls.filter((c) => /^w\d-/.test(c.label) && !c.label.endsWith(':record')).every((c) => c.opts.isolation === 'worktree'))
    ok('fresh: script nodes go to the project runner on their declared model',
      calls.filter((c) => c.label === 'preflight' || c.label.startsWith('gate-')).every((c) => c.opts.agentType === 'rebuild-cli-runner' && c.opts.model === 'haiku'))
    ok('fresh: both waves recorded done', result.state.waves['1'].status === 'done' && result.state.waves['2'].status === 'done', result.state)
    ok('fresh: the fixer is skipped when review is not blocking', !labels.includes('fix'), labels)
    ok('fresh: every dispatched schema is strict, with no JSON-in-a-string', calls.every((c) => strictSchema(c.opts.schema)), calls.map((c) => c.label))
    ok('fresh: a node\'s declared effort is passed on its dispatch, an undeclared one is not invented',
      calls.find((c) => c.label === 'w1-render').opts.effort === 'high' && calls.find((c) => c.label === 'smoke').opts.effort === undefined,
      calls.filter((c) => c.label === 'w1-render' || c.label === 'smoke').map((c) => c.opts))
    const gateCmd = cmdOf(calls.find((c) => c.label === 'gate-1:s0').prompt)
    ok('fresh: gate command carries the stage\'s rows as row=branch pairs',
      gateCmd.includes('--branches w1-parse=agent/w1-parse,w1-render=agent/w1-render') && gateCmd.includes('--final 1'), gateCmd)
  }

  // 2. #106 R3: a finished wave is skipped BEFORE any of its builders is dispatched.
  {
    const state = { waves: { 1: { status: 'done', integrationSha: 'I-wave1' } } }
    const { result, calls } = await execute({ plan: clone(PLAN), state }, happy)
    const labels = calls.map((c) => c.label)
    ok('resume: no wave-1 builder is dispatched', !labels.some((l) => l.startsWith('w1-') || l.startsWith('gate-1')), labels)
    ok('resume: wave 2 starts from the recorded integration sha', baseOf(calls.find((c) => c.label === 'w2-cli').prompt) === 'I-wave1')
    ok('resume: completes', result && !result.aborted, result)
  }

  // 3. #106 R3: a finished builder survives a restart; its branch is still merged.
  {
    const state = { builders: { 'w1-parse': { branch: 'agent/w1-parse-old', base: 'H0', notes: ['kept note'] } } }
    const { calls } = await execute({ plan: clone(PLAN), state }, happy)
    const labels = calls.map((c) => c.label)
    ok('restart: the recorded builder is not re-dispatched', !labels.includes('w1-parse') && labels.includes('w1-render'), labels)
    ok('restart: its recorded branch is what the gate merges',
      cmdOf(calls.find((c) => c.label === 'gate-1:s0').prompt).includes('w1-parse=agent/w1-parse-old'))
  }

  // 4. #106 R1: a builder that started from anywhere but the wave base halts the run.
  {
    const { result, calls } = await execute({ plan: clone(PLAN) }, (l, p, o) => (l === 'w1-render' ? { branch: 'agent/w1-render', baseSha: 'SOMEWHERE-ELSE', notes: [] } : happy(l, p, o)))
    ok('base: a wrong baseSha halts', result.aborted && /WRONG BASE/.test(result.abortReason), result)
    ok('base: nothing is merged after a wrong base', !calls.some((c) => c.label.startsWith('gate-')), calls.map((c) => c.label))
  }

  // 5. #106 R1: launched from a linked worktree, or with a dirty primary checkout.
  {
    const linked = await execute({ plan: clone(PLAN) }, (l, p, o) => (l === 'preflight' ? script({ linkedWorktree: true, dirty: false, head: 'H0', python: '3.12' }) : happy(l, p, o)))
    ok('preflight: a linked worktree halts before any builder', linked.result.aborted && /PRIMARY CHECKOUT ONLY/.test(linked.result.abortReason) && linked.calls.length === 1, linked.result)
    const dirty = await execute({ plan: clone(PLAN) }, (l, p, o) => (l === 'preflight' ? script({ linkedWorktree: false, dirty: true, head: 'H0', python: '3.12' }) : happy(l, p, o)))
    ok('preflight: a dirty primary checkout halts', dirty.result.aborted && dirty.calls.length === 1, dirty.result)
  }

  // 6. #106 R4/R5: a red gate stops the run with the target unmoved and everything kept.
  {
    const red = script({ green: false, integrationSha: 'I-red', targetMoved: false, findings: [{ gate: 'test', source: 'primary-only', exit: 1 }], kept: ['agent/w1-parse', 'agent/w1-render'] }, 1)
    const { result, calls } = await execute({ plan: clone(PLAN) }, (l, p, o) => (l === 'gate-1:s0' ? red : happy(l, p, o)))
    ok('red gate: the run stops', result.aborted && /RED/.test(result.abortReason), result)
    ok('red gate: no wave-2 builder is dispatched', !calls.some((c) => c.label.startsWith('w2-')))
    ok('red gate: the wave is not marked done', !result.state.waves['1'])
    ok('red gate: findings keep their primary-only source and the kept worktrees are named',
      result.findings[0].source === 'primary-only' && result.kept.length === 2, result)
  }

  // 7. #106 R7: a swarm row -- same prompt, blind referee, loser never merged.
  {
    const plan = clone(PLAN)
    const row = plan.nodes.find((n) => n.id === 'w1-parse')
    row.swarm = 3
    row.referee = { model: 'opus', agentType: 'rebuild-cli-referee' }
    const { result, calls } = await execute({ plan }, (l, p, o) => (l === 'w1-parse:referee'
      ? { winner: 'agent/w1-parse-c2', perCandidate: [] }
      : happy(l, p, o)))
    const cands = calls.filter((c) => /^w1-parse:c\d$/.test(c.label))
    ok('swarm: N candidates dispatched', cands.length === 3, calls.map((c) => c.label))
    const strip = (p) => p.replace(/candidate c\d for /, '')
    ok('swarm: every candidate gets the same prompt', cands.every((c) => strip(c.prompt) === strip(cands[0].prompt)))
    const ref = calls.find((c) => c.label === 'w1-parse:referee').prompt
    ok('swarm: the referee sees branch names and acceptance commands, never the goal or notes',
      ref.includes('agent/w1-parse-c1') && ref.includes('go test ./internal/parse/...') && !ref.includes(row.goal) && !ref.includes('done w1-parse'), ref)
    const gateCmd = cmdOf(calls.find((c) => c.label === 'gate-1:s0').prompt)
    ok('swarm: only the winner is merged', gateCmd.includes('w1-parse=agent/w1-parse-c2') && !gateCmd.includes('w1-parse=agent/w1-parse-c1'), gateCmd)
    ok('swarm: the losers are handed over for discarding', /--discard agent\/w1-parse-c1,agent\/w1-parse-c3/.test(gateCmd), gateCmd)
    ok('swarm: completes', !result.aborted, result)
  }
  {
    const plan = clone(PLAN)
    const row = plan.nodes.find((n) => n.id === 'w1-parse')
    row.swarm = 2
    row.referee = { model: 'opus', agentType: 'rebuild-cli-referee' }
    const { result } = await execute({ plan }, (l, p, o) => (l === 'w1-parse:referee' ? { winner: null, perCandidate: [] } : happy(l, p, o)))
    ok('swarm: no accepted candidate halts', result.aborted && /NO CANDIDATE ACCEPTED/.test(result.abortReason), result)
  }

  // 8. #106 R8: prompts carry ids and branch names, never a sibling's content.
  {
    const { calls } = await execute({ plan: clone(PLAN) }, happy)
    const rows = PLAN.nodes.filter((n) => Number.isInteger(n.wave) && n.kind === 'agent')
    let leak = null
    for (const c of calls) {
      const self = rows.find((r) => r.id === c.label)
      if (!self) continue
      for (const other of rows) {
        if (other.id !== self.id && (c.prompt.includes(other.goal) || c.prompt.includes(`done ${other.id}`))) leak = [self.id, other.id]
      }
    }
    ok('hygiene: no builder prompt carries another row\'s goal or notes', leak === null, leak)
  }

  // 9. #106 comment item 6: smoke runs outside the repository.
  {
    const { calls } = await execute({ plan: clone(PLAN) }, happy)
    const smoke = calls.find((c) => c.label === 'smoke')
    ok('smoke: told to work in a scratch directory OUTSIDE the repository, with the declared steps',
      /OUTSIDE this repository/.test(smoke.prompt) && smoke.prompt.includes('go run ./cmd/tool --help') && smoke.opts.isolation === undefined, smoke.prompt)
  }

  // 10. #106 comment item 1: state as a JSON string is refused, not parsed.
  {
    const { threw } = await execute(JSON.stringify({ plan: PLAN, state: {} }), happy)
    ok('args: a JSON string is refused', threw && /string/.test(String(threw)), String(threw))
  }

  // 11. #107: a human gate stops the run between waves until it is approved.
  {
    const plan = clone(PLAN)
    plan.nodes.push({ id: 'approve', kind: 'human-gate', goal: 'sign off wave 1', depends_on: ['gate-1'] })
    for (const n of plan.nodes) if (n.wave === 2) n.depends_on = [...n.depends_on, 'approve']
    const pending = await execute({ plan }, happy)
    ok('human gate: the run returns pending before wave 2', pending.result.pending_human_gate === 'approve'
      && !pending.calls.some((c) => c.label.startsWith('w2-')), pending.result)
    ok('human gate: wave 1 finished and is recorded', pending.result.state.waves['1'].status === 'done')
    const resumed = await execute({ plan, state: { ...pending.result.state, approvals: { approve: true } } }, happy)
    ok('human gate: approved, the next launch skips wave 1 and builds wave 2',
      !resumed.calls.some((c) => c.label === 'w1-parse') && resumed.calls.some((c) => c.label === 'w2-cli') && !resumed.result.aborted, resumed.result)
  }

  // 12. One fix round: a blocking review dispatches the fixer, whose branch is gated again.
  {
    const { result, calls } = await execute({ plan: clone(PLAN) }, (l, p, o) => (l === 'review' ? { blocking: true, findings: ['x'] } : happy(l, p, o)))
    const labels = calls.map((c) => c.label)
    ok('fix: dispatched in a worktree on the integration head', labels.includes('fix')
      && calls.find((c) => c.label === 'fix').opts.isolation === 'worktree', labels)
    ok('fix: its branch goes through the last merge-gate', labels.includes('gate-2:fix')
      && cmdOf(calls.find((c) => c.label === 'gate-2:fix').prompt).includes('--branches fix=agent/fix'), labels)
    ok('fix: completes', !result.aborted, result)
  }

  // 13. The runner guard's character class, enforced before dispatch.
  {
    const { result, calls } = await execute({ plan: clone(PLAN) }, (l, p, o) => (l === 'w1-parse' ? { branch: 'x;rm -rf .', baseSha: 'H0', notes: [] } : happy(l, p, o)))
    ok('placeholder: an unsafe branch name halts before it reaches a command', result.aborted
      && !calls.some((c) => c.label === 'w1-parse:record'), result)
  }

  {
    // A branch arriving from RESUMED state never passed build()'s check; the
    // script runner's own placeholder check is the only thing between it and a command.
    const state = { builders: { 'w1-parse': { branch: 'agent/x;rm -rf .', base: 'H0', notes: [] } } }
    const { result, calls } = await execute({ plan: clone(PLAN), state }, happy)
    ok('placeholder: an unsafe branch from resumed state halts before the merge-gate runs', result.aborted
      && /refuses/.test(result.abortReason) && !calls.some((c) => c.label.startsWith('gate-1')), result)
  }

  // 14. Integrator stages (the Rust fixture): rows first, the integrator on their merge.
  {
    const { result, calls } = await execute({ plan: planOf(RUST) }, (l, p, o) => (l === 'w1-eval:referee'
      ? { winner: 'agent/w1-eval-c1', perCandidate: [] } : happy(l, p, o)))
    const labels = calls.map((c) => c.label)
    ok('stages: the concurrent rows merge (non-final) before the integrator starts',
      labels.indexOf('gate-1:s0') < labels.indexOf('w1-register') && / --final 0 /.test(`${cmdOf(calls.find((c) => c.label === 'gate-1:s0').prompt)} `), labels)
    ok('stages: the integrator builds on the stage-0 merge', baseOf(calls.find((c) => c.label === 'w1-register').prompt) === 'I-gate1s0')
    ok('stages: the final stage gates and completes', labels.includes('gate-1:s1') && !result.aborted, result)
    ok('stages: a declared smoke skip reports without a scratch build', /declares no steps/.test(calls.find((c) => c.label === 'smoke').prompt))
  }

  await authoredSuite()
}

async function authoredSuite() {
  // 15. Authored steps: written and verified before anything could run them.
  {
    const { result, calls } = await execute({ plan: planOf(AUTHORED), state: {} }, happy)
    const labels = calls.map((c) => c.label)
    ok('author: the step is written, then verified, before the preflight',
      labels[0] === 'api-surface:author' && labels[1] === 'api-surface:verify' && labels[2] === 'preflight', labels)
    const a = calls.find((c) => c.label === 'api-surface:author')
    ok('author: dispatched to the plan\'s author agent on its declared model',
      a.opts.agentType === 'rebuild-cli-author' && a.opts.model === 'sonnet' && strictSchema(a.opts.schema), a.opts)
    ok('author: the prompt names the one file, its command, its schema and the sample',
      a.prompt.includes(STEP_FILE) && a.prompt.includes('python3 .claude/workflows/rebuild-cli.steps/api-surface.py cmd/tool')
      && a.prompt.includes('"exported"') && a.prompt.includes('["cmd/tool"]'), a.prompt)
    ok('author: the prompt carries no other node\'s goal',
      !AUTHORED.nodes.some((n) => n.id !== 'api-surface' && a.prompt.includes(n.goal)), a.prompt)
    const v = calls.find((c) => c.label === 'api-surface:verify')
    ok('author: verify-step runs through the runner with the node filled in',
      v.opts.agentType === 'rebuild-cli-runner' && cmdOf(v.prompt) === 'python3 .claude/workflows/rebuild-cli_state.py verify-step --node api-surface', v.prompt)
    ok('author: the step itself runs after the last gate', labels.indexOf('api-surface') > labels.indexOf('gate-2:s0'), labels)
    ok('author: completes, with the step recorded verified', !result.aborted && result.state.steps['api-surface'].status === 'verified', result)
  }
  {
    const { calls } = await execute({ plan: planOf(AUTHORED), state: { steps: { 'api-surface': { status: 'verified' } } } }, happy)
    const labels = calls.map((c) => c.label)
    ok('author: a verified step is not re-authored on resume', !labels.some((l) => /:author|:verify/.test(l)) && labels.includes('api-surface'), labels)
  }
  {
    const { calls } = await execute({ plan: planOf(AUTHORED), state: { steps: { 'api-surface': { status: 'stale' } } } }, happy)
    ok('author: a stale step is rewritten', calls.some((c) => c.label === 'api-surface:author'), calls.map((c) => c.label))
  }
  {
    const plan = planOf(AUTHORED)
    plan.nodes.find((n) => n.id === 'api-surface').retries = 1
    let first = true
    const { result, calls } = await execute({ plan }, (l, p, o) => {
      if (l === 'api-surface:verify' && first) {
        first = false
        return script({ verified: false, node: 'api-surface', path: STEP_FILE, problem: 'sample: stdout breaks output_schema: stdout.exported: required, missing' }, 1)
      }
      return happy(l, p, o)
    })
    const second = calls.find((c) => c.label === 'api-surface:author:2')
    ok('author: a refusal is fed back to a fresh author dispatch', second && second.prompt.includes('stdout.exported: required, missing'), calls.map((c) => c.label))
    ok('author: the first prompt carried no refusal', !calls.find((c) => c.label === 'api-surface:author').prompt.includes('was refused'))
    ok('author: the retried step verifies and the run completes', !result.aborted, result)
  }
  {
    const { result, calls } = await execute({ plan: planOf(AUTHORED) }, (l, p, o) => (/^api-surface:verify/.test(l)
      ? script({ verified: false, node: 'api-surface', path: STEP_FILE, problem: 'syntax: invalid syntax' }, 1) : happy(l, p, o)))
    ok('author: out of retries, the run stops with AUTHOR CONTRACT before the preflight',
      result.aborted && /AUTHOR CONTRACT -- syntax/.test(result.abortReason) && !calls.some((c) => c.label === 'preflight'), result)
  }
  {
    const { result, calls } = await execute({ plan: planOf(AUTHORED) }, (l, p, o) => (/^api-surface:author/.test(l)
      ? { path: 'somewhere/else.py', notes: '' } : happy(l, p, o)))
    ok('author: a file other than the declared one is not verified, and stops the run',
      result.aborted && /not \.claude/.test(result.abortReason) && !calls.some((c) => /:verify/.test(c.label)), result)
  }
  {
    // Two authored steps, timed: the fast one's verify must start while the
    // slow one is still being written (no barrier), and no two verifies may
    // ever be in flight at once (they share the state file).
    const plan = planOf(AUTHORED)
    const twin = clone(plan.nodes.find((n) => n.id === 'api-surface'))
    twin.id = 'api-surface-2'
    twin.script.command = 'python3 .claude/workflows/rebuild-cli.steps/api-surface-2.py cmd/tool'
    plan.nodes.push(twin)
    const events = []
    let inflight = 0
    let most = 0
    const wait = (ms) => new Promise((r) => setTimeout(r, ms))
    const { result } = await execute({ plan }, async (l, p, o) => {
      events.push(`start:${l}`)
      let out
      if (/:verify/.test(l)) {
        inflight += 1
        most = Math.max(most, inflight)
        await wait(20)
        inflight -= 1
        const node = l.split(':')[0]
        out = script({ verified: true, node, path: `.claude/workflows/rebuild-cli.steps/${node}.py`, problem: '' })
      } else if (/:author/.test(l)) {
        const node = l.split(':')[0]
        await wait(node === 'api-surface' ? 5 : 15)
        out = { path: `.claude/workflows/rebuild-cli.steps/${node}.py`, notes: '' }
      } else if (l === 'api-surface-2') {
        out = script({ package: 'cmd/tool', exported: [] })
      } else {
        out = happy(l, p, o)
      }
      events.push(`end:${l}`)
      return out
    })
    ok('author: two steps verify one at a time', most === 1, { most, events })
    ok('author: a fast step is verified while a slow one is still being written',
      events.indexOf('start:api-surface:verify') < events.indexOf('end:api-surface-2:author'), events)
    ok('author: both steps verified, run completes', !result.aborted
      && result.state.steps['api-surface'].status === 'verified' && result.state.steps['api-surface-2'].status === 'verified', result)
  }
  {
    const plan = planOf(AUTHORED)
    delete plan.authorAgent
    const { result, calls } = await execute({ plan }, happy)
    ok('author: a plan without an author agent stops before any dispatch', result.aborted && calls.length === 0, result)
  }
  {
    const plan = planOf(AUTHORED)
    delete plan.nodes.find((n) => n.id === 'api-surface').script.author.model
    const { result, calls } = await execute({ plan }, happy)
    ok('author: an author without a model stops before any dispatch', result.aborted && /author\.model/.test(result.abortReason) && calls.length === 0, result)
  }
}

async function main() {
  await suite()
  console.log()
  if (failures.length) {
    console.log(`FAILED ${failures.length} of ${count}: ${failures.join(', ')}`)
    process.exit(1)
  }
  console.log(`waves.js: ${count} assertions passed against stub hooks (no tokens spent)`)
  const uncaught = []
  quiet = true
  for (const [name, find, repl] of SABOTAGE) {
    if (!BODY.includes(find)) {
      console.log(`  FAIL sabotage '${name}': its anchor is not in waves.js, so it would plant nothing`)
      uncaught.push(name)
      continue
    }
    body = BODY.replace(find, repl)
    failures = []
    let threw = false
    try { await suite() } catch { threw = true }
    const caught = threw || failures.length > 0
    console.log(`  ${caught ? 'ok  ' : 'FAIL'} sabotage '${name}' -> ${threw ? 'threw' : `${failures.length} case(s) red`}`)
    if (!caught) uncaught.push(name)
  }
  body = BODY
  if (uncaught.length) {
    console.log(`\nsabotage NOT caught: ${uncaught.join(', ')}`)
    process.exit(1)
  }
  console.log(`sabotage: ${SABOTAGE.length} planted defects, each turned the suite red`)
}

main()
