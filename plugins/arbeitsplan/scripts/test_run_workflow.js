#!/usr/bin/env node
// Executes workflows/run.js against stub agent()/parallel()/phase()/log() hooks.
//
// usage: node plugins/arbeitsplan/scripts/test_run_workflow.js
//
// No tokens, no Workflow tool. run.js is evaluated exactly as the runtime
// evaluates it -- `meta`'s export stripped, the body compiled as an async
// function with the hooks as parameters -- so a control-flow defect (a plan
// phase dispatched, a budget overrun, a borrowed hunk outside the gate, a
// gating value silently defaulted) shows up as a failed assertion here instead
// of as a spent run. The stubs answer by label, so each case says precisely
// what every agent returned.
//
// Then it sabotages itself: each SABOTAGE plants one defect into run.js in
// memory and the suite must go red, or the case that should catch it is not
// catching anything.
//
// Exit: 0 every case passed and every sabotage was caught, 1 otherwise.
'use strict'

const fs = require('node:fs')
const path = require('node:path')

const ROOT = path.resolve(__dirname, '..')
const SRC = fs.readFileSync(path.join(ROOT, 'workflows', 'run.js'), 'utf8')
const SIX = JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures', 'six-phase.workflow.json'), 'utf8'))
const AsyncFunction = Object.getPrototypeOf(async () => {}).constructor
const BODY = SRC.replace(/^export\s+(?=const\s+meta\b)/m, '')
let body = BODY
let quiet = false
const STATUSES = new Set(['proposed', 'accepted', 'refuted', 'doubt', 'unmeasured', 'opened', 'closed', 'pending', 'halted'])

const clone = (o) => JSON.parse(JSON.stringify(o))

// answer(label, prompt, opts) -> the object the agent "returns", or null.
async function execute(args, answer) {
  const calls = []
  const agent = async (prompt, opts) => {
    calls.push({ label: opts.label, opts, prompt })
    return answer(opts.label, prompt, opts)
  }
  const parallel = async (thunks) => Promise.all(thunks.map((t) => t().catch(() => null)))
  const fn = new AsyncFunction('args', 'agent', 'parallel', 'pipeline', 'phase', 'log', 'budget', body)
  const result = await fn(args, agent, parallel, null, () => {}, () => {}, { total: null })
  return { result, calls }
}

const inventory = (label) => ({ source: label, items: [{ id: 'i1', path: 'src/a.py' }], truncated: false, stoppedAt: null })
const candidate = (diff = 'diff --git a/src/x.py b/src/x.py\n+ok') => ({
  candidateId: 'IGNORED', measured: true, diff, filesTouched: ['src/x.py'], checks: [{ id: 'a1', command: 'true', exit: 0 }], outOfScopeWrites: [],
})
const accept = { candidateId: 'IGNORED', verdict: 'accepted', perCriterion: [{ id: 'a1', met: true, evidence: 'exit 0' }] }
const synth = { baseCandidateId: 'c1', diff: 'diff', borrowed: [], filesTouched: ['src/x.py'], cannotEstablish: [] }

function happy(label) {
  if (label.startsWith('inventory:')) return inventory(label)
  if (label.startsWith('build:')) return candidate()
  if (label.startsWith('referee:')) return clone(accept)
  if (label === 'synthesize') return clone(synth)
  return null
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

// [name, exact text in run.js, replacement]. An exact match is REQUIRED -- a
// sabotage whose anchor no longer exists would plant nothing and pass vacuously.
const SABOTAGE = [
  ['plan-node stop removed', "if (ph.mode === 'plan') {", 'if (false) {'],
  ['budget never refuses', 'if (dispatched + n > ceiling)', 'if (false)'],
  ['borrow gate ignored', 'const illegal = (out.borrowed || []).filter((b) => !gate.includes(b.beatsOn))', 'const illegal = []'],
  ['modelTier defaulted', "if (!['haiku', 'sonnet', 'opus'].includes(ph.modelTier)) {", "if (!(ph.modelTier = ph.modelTier || 'sonnet')) {"],
  ['unmeasured counted as failure', 'const measured = results.filter((r) => r.measured !== false)', 'const measured = results'],
  ['builder identity overwritable', '.then((r) => (r ? { ...r, candidateId: id, angle } : null))', '.then((r) => (r ? { candidateId: id, angle, ...r } : null))'],
  ['re-derivation skipped', 'const sample = rd ? sampleIndices(sources.length, rd.samplePct, rd.seed) : []', 'const sample = []'],
  ['shared writer allowed', "if (ph.writes === 'shared') {", 'if (false) {'],
  ['forgotten-work check skipped', 'if (FORGETFUL.test(ph.agentType)) {', 'if (false) {'],
  // #81: back to a command sharing a line with the criterion prose -- the exact
  // defect the fenced-block rendering exists to prevent.
  ['acceptance checks rendered inline again (#81)',
    "return cmds.length ? [header, '  ```', ...cmds.map((cmd) => `  ${cmd}`), '  ```'].join('\\n') : header",
    "return cmds.length ? header + ' [[' + cmds.join(', ') + ']]' : header"],
  // Payloads back on events: a referee's evidence, a builder's commands.
  ['referee event carries full perCriterion again',
    'unmet: (v && Array.isArray(v.perCriterion) ? v.perCriterion : []).filter((p) => p && p.met === false).map((p) => p.id),',
    'perCriterion: v ? v.perCriterion : [],'],
  ['builder event carries full check commands again',
    'checks: (r.checks || []).map((k) => ({ id: k.id, exit: k.exit })) }, phaseSpan)',
    'checks: r.checks || [] }, phaseSpan)'],
]

async function suite() {
  // 1. From the top: INVENTORY runs, then the workflow stops before CONTRACT.
  {
    const { result, calls } = await execute({ spec: clone(SIX) }, happy)
    ok('halts before the first plan-mode phase', result.pending_plan_node === 'contract', result)
    ok('names the phase to resume from', result.resumeWith === 'build', result.resumeWith)
    ok('never dispatches a plan-mode agent', !calls.some((c) => /contract|adjudicat/.test(c.opts.agentType)), calls.map((c) => c.label))
    // 4 partitions + ceil(4 * 25%) = 1 re-derivation.
    ok('inventory dispatches 4 extractors and 1 re-derivation', calls.length === 5 && result.dispatched === 5, calls.map((c) => c.label))
    ok('every dispatch carries the phase modelTier, never a default', calls.every((c) => c.opts.model === 'haiku'), calls.map((c) => c.opts.model))
    ok('agreeing re-derivation records accepted, not doubt',
      result.events.some((e) => e.span === 'evaluation' && e.node_id === 'inventory' && e.status === 'accepted'), result.events)
  }

  // 2. Resumed after CONTRACT: BUILD, REFEREE, SYNTHESIZE, then stop before ADJUDICATE.
  {
    const carry = { contract: { acceptance: SIX.problem.acceptance } }
    const { result, calls } = await execute({ spec: clone(SIX), startAt: 'build', carry }, happy)
    ok('resumes and stops before ADJUDICATE', result.pending_plan_node === 'adjudicate', result)
    ok('build+referee+synthesize = 7 dispatches', result.dispatched === 7, result.dispatched)
    ok('builders run in worktree isolation', calls.filter((c) => c.label.startsWith('build:')).every((c) => c.opts.isolation === 'worktree'))
    ok('referees are never isolated writers', calls.filter((c) => c.label.startsWith('referee:')).every((c) => c.opts.isolation === undefined))
    ok('a builder cannot overwrite its own candidateId', result.carry.build.candidates.map((c) => c.candidateId).join() === 'c1,c2,c3')
    ok('winner selected by rule (id tie-break)', result.carry.referee.winner === 'c1', result.carry.referee)
    const refereePrompt = calls.find((c) => c.label === 'referee:c1').prompt
    ok('the referee never sees the builder angle', !/Your angle/.test(refereePrompt) && !refereePrompt.includes(' x\n'))
  }

  // 3. The budget the hook cannot see is enforced in code.
  {
    const spec = clone(SIX)
    spec.budget.totalDispatches = 3
    const { result, calls } = await execute({ spec }, happy)
    ok('budget ceiling halts before dispatching past it', result.aborted && /budget/.test(result.abortReason) && calls.length === 0, result)
  }

  // 4. The breaker: 2 of 3 measured builders out of scope.
  {
    const { result } = await execute({ spec: clone(SIX), startAt: 'build' }, (label) => {
      if (label === 'build:c2' || label === 'build:c3') return { ...candidate(), outOfScopeWrites: ['secrets.py'] }
      return happy(label)
    })
    ok('breaker halts on 1/3 usable', result.aborted && /CONTRACT PROBLEM/.test(result.abortReason), result.abortReason)
    ok('the halt is an event, not an absence', result.events.some((e) => e.span === 'halt' && e.status === 'halted'))
  }

  // 5. Unmeasured candidates leave the denominator.
  {
    const { result } = await execute({ spec: clone(SIX), startAt: 'build' }, (label) => {
      // TWO unmeasured: 1/1 measured passes a 2/3 breaker, 1/3 would trip it. One
      // unmeasured was too weak -- 2/3 clears 2/3 either way, and the sabotage run
      // proved this case could not tell the two apart.
      if (label === 'build:c2' || label === 'build:c3') return { candidateId: 'x', measured: false, diff: null }
      return happy(label)
    })
    ok('1 usable of 1 measured passes the breaker despite 2 unmeasured', result.pending_plan_node === 'adjudicate', result.abortReason)
    ok('the unmeasured candidate is recorded as unmeasured',
      result.events.some((e) => e.node_id === 'build:c3' && e.status === 'unmeasured'))
  }

  // 6. A borrowed hunk outside the gate is refused in code.
  {
    const { result } = await execute({ spec: clone(SIX), startAt: 'build' }, (label) => {
      if (label === 'synthesize') return { ...clone(synth), borrowed: [{ from: 'c2', beatsOn: 'a1', hunk: 'h' }] }
      return happy(label)
    })
    ok('borrow on a criterion outside borrowGate halts', result.aborted && /borrowGate/.test(result.abortReason), result.abortReason)
  }

  // 7. Re-derivation disagreement is doubt, carrying resolves_if.
  {
    let n = 0
    const { result } = await execute({ spec: clone(SIX) }, (label) => {
      if (label.startsWith('inventory:rederive')) { n += 1; return { source: 's', items: [{ id: 'other', path: 'p' }], truncated: false } }
      return happy(label)
    })
    const ev = result.events.find((e) => e.span === 'evaluation' && e.node_id === 'inventory')
    ok('a disagreeing re-derivation is recorded as doubt', n === 1 && ev && ev.status === 'doubt' && ev.detail.resolves_if, ev)
  }

  // 8. No gating value is inferred.
  {
    const spec = clone(SIX)
    delete spec.phases[0].modelTier
    const { result, calls } = await execute({ spec }, happy)
    ok('a phase without modelTier halts instead of defaulting to sonnet', result.aborted && calls.length === 0, result)
  }

  // 9. The spec is re-checked, not trusted.
  {
    const a = await execute({ spec: { ...clone(SIX), backend: { kind: 'in-session', why: ['script-sequence'] } } }, happy)
    ok('a non-workflow spec is refused', !!a.result.error && a.calls.length === 0, a.result)
    const spec = clone(SIX)
    spec.phases[4].writes = 'shared'
    const b = await execute({ spec, startAt: 'build' }, happy)
    ok('a shared-tree writer halts inside the workflow', b.result.aborted && b.result.haltedAt === 'synthesize', b.result)
    const c = await execute({ spec: { ...clone(SIX), schemaVersion: '1' } }, happy)
    ok('schemaVersion 1 is refused', !!c.result.error, c.result)
  }

  // 10. Every event is span-shaped, with a status from the closed set.
  {
    const { result } = await execute({ spec: clone(SIX), startAt: 'build' }, happy)
    const bad = result.events.filter((e) => !e.trace_id || !e.span_id || !e.parent_span_id || !e.span || !e.node_id || !STATUSES.has(e.status))
    ok('every event carries trace/span/parent/node ids and a known status', bad.length === 0, bad)
    ok('span ids are unique', new Set(result.events.map((e) => e.span_id)).size === result.events.length)
  }

  // 12. An implementer that leaves a forgotten-work key blank is halted in code.
  {
    const spec = clone(SIX)
    spec.phases = [{ id: 'impl', kind: 'single-writer', pattern: 'best-of-n', modelTier: 'sonnet', mode: 'auto', writes: 'worktree', agentType: 'arbeitsplan:implementer', requires: [], marker: 'implemented' }]
    const full = { rollback: 'git revert', docsSync: 'n/a: no docs', contractSync: 'n/a: none', deadArtifacts: 'n/a: none', releaseWiring: 'n/a: internal' }
    const a = await execute({ spec }, () => ({ diff: 'd', forgotten: { ...full, docsSync: '' } }))
    ok('a blank forgotten-work key halts the implementer', a.result.aborted && /docsSync/.test(a.result.abortReason), a.result)
    const b = await execute({ spec }, () => ({ diff: 'd', forgotten: full }))
    ok('a fully answered implementer completes', !b.result.aborted && b.result.completed.join() === 'impl', b.result)
  }

  // 11. Every doubt carries resolves_if -- run_record.py refuses one that does not,
  // so a doubt run.js emits without it would be lost at persistence time.
  {
    const { result } = await execute({ spec: clone(SIX) }, (label) => {
      if (label === 'inventory:2') return { ...inventory(label), truncated: true, stoppedAt: 'src/b/z.py' }
      return happy(label)
    })
    const r2 = await execute({ spec: clone(SIX), startAt: 'build' }, (label) => {
      if (label === 'referee:c3') return { candidateId: 'x', verdict: 'cannot_judge', perCriterion: [] }
      return happy(label)
    })
    const doubts = [...result.events, ...r2.result.events].filter((e) => e.status === 'doubt')
    ok('doubts were produced to check', doubts.length >= 2, doubts)
    ok('every doubt carries detail.resolves_if', doubts.every((e) => e.detail && e.detail.resolves_if), doubts)
  }

  // 16. Every event fits ONE atomic run.jsonl line. record_event.py appends each as
  // a line of at most 4096 bytes and refuses a result holding a larger one, so a
  // payload -- commands, evidence, hunks, long path lists -- never rides an event.
  {
    const cmd = 'python3 /a/long/absolute/path/to/analysis/arbeitsplan/ap-x/checks/probe_w9.py . --only a-long-mode'
    const ids = Array.from({ length: 40 }, (_, i) => `w${i}`)
    const { result } = await execute({ spec: clone(SIX), startAt: 'build' }, (label) => {
      if (label.startsWith('build:')) {
        return { ...candidate(), filesTouched: ids.map((i) => `plugins/some/deep/path/${i}.py`),
          checks: ids.map((id) => ({ id, command: cmd, exit: 0 })) }
      }
      if (label.startsWith('referee:')) {
        return { candidateId: 'x', verdict: 'accepted', perCriterion: ids.map((id) => ({ id, met: true, evidence: 'e'.repeat(200) })) }
      }
      return happy(label)
    })
    const bytes = (e) => Buffer.byteLength(`${JSON.stringify({ kind: 'event', at: '2026-01-01T00:00:00+00:00', ...e })}\n`)
    const worst = result.events.reduce((m, e) => Math.max(m, bytes(e)), 0)
    ok('events were produced to measure', result.events.length > 5, result.events.length)
    ok('every event fits one 4096-byte run.jsonl line, even with 40 long criteria', worst <= 4096, worst)
  }

  // 13. #81: every acceptance command stands alone on its own line inside a
  // fenced block -- never trailing the criterion text in a parenthesised
  // clause on the same line -- and an array check's every element gets its
  // own line, in both the builder prompt and the referee prompt (criteria
  // AND the builder-reported checks the referee is also shown).
  {
    const spec = clone(SIX)
    // The literal old marker is built by concatenation, never written as one
    // substring in this file: a lint rule elsewhere in this repo bans the old
    // rendering's exact text everywhere outside CHANGELOG.md, this file included.
    const oldForm = '(' + 'check: '
    const parenCmd = "git diff --exit-code -- requirements.txt && echo '(ok)'"
    const arrCmds = ['pytest -q tests/test_x.py', 'pytest -q tests/test_y.py']
    spec.problem.acceptance = [
      { id: 'a1', criterion: 'no new runtime dependency', check: parenCmd },
      { id: 'a2', criterion: 'both suites pass', check: arrCmds },
    ]
    const carry = { contract: { acceptance: spec.problem.acceptance } }
    const reportedChecks = [
      { id: 'a1', command: parenCmd, exit: 0 },
      { id: 'a2', command: arrCmds[0], exit: 0 },
      { id: 'a2', command: arrCmds[1], exit: 0 },
    ]
    const { calls } = await execute({ spec, startAt: 'build', carry }, (label) => {
      if (label.startsWith('build:')) return { ...candidate(), checks: reportedChecks }
      return happy(label)
    })
    const buildPrompt = calls.find((c) => c.label === 'build:c1').prompt
    const refereePrompt = calls.find((c) => c.label === 'referee:c1').prompt
    const lines = (s) => s.split('\n').map((l) => l.trim())
    for (const [name, prompt] of [['builder', buildPrompt], ['referee', refereePrompt]]) {
      ok(`${name} prompt: no line renders the old parenthesised form`, !prompt.includes(oldForm), prompt)
      ok(`${name} prompt: the multi-word command with its own parens stands alone on its own line`,
        lines(prompt).includes(parenCmd), prompt)
      ok(`${name} prompt: every array element stands alone on its own line`,
        arrCmds.every((c) => lines(prompt).includes(c)), prompt)
    }
    const reportedSection = refereePrompt.split('Checks the builder reported:')[1] || ''
    ok('referee prompt: the builder-reported command list also fences each command on its own line',
      lines(reportedSection).includes(parenCmd), reportedSection)
    ok('referee prompt: a reported command never shares its line with "-> exit"',
      !reportedSection.split('\n').some((l) => l.includes('->') && /exit/.test(l)), reportedSection)
  }

}

async function main() {
  await suite()
  const total = count
  const real = failures
  console.log()
  if (real.length) {
    console.log(`FAILED ${real.length} of ${total}: ${real.join(', ')}`)
    process.exit(1)
  }
  console.log(`run.js: ${total} assertions passed against stub hooks (no tokens spent)`)

  const uncaught = []
  quiet = true
  for (const [name, find, repl] of SABOTAGE) {
    if (!BODY.includes(find)) {
      console.log(`  FAIL sabotage '${name}': its anchor is not in run.js, so it would plant nothing`)
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
    console.log(`SABOTAGE NOT CAUGHT (${uncaught.length}): ${uncaught.join(', ')}`)
    process.exit(1)
  }
  console.log(`sabotage: ${SABOTAGE.length} planted defects, each turned the suite red`)
}

main().catch((e) => {
  console.error(e)
  process.exit(1)
})
