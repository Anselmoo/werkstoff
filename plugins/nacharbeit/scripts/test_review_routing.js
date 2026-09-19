#!/usr/bin/env node
// Executes workflows/review.js against stub agent()/parallel()/pipeline() hooks and
// asserts what it does with the routing simulation. No tokens, no Workflow tool.
//
// usage: node plugins/nacharbeit/scripts/test_review_routing.js
//
// The corpus is two skills, s1 and s2. Five documented prompts name s1, one names
// s2; one of s1's prompts (k5) routes to s2, and an ambiguous prompt picks both, so
// the pair is judged -- and the stub judge calls it an 'intended-handoff'. With the
// router above the 0.8 floor that must yield a Q-ROUTE-MISS and a Q-CANN-CAPTURE on
// s1; below it, neither, and the skipped rules are named. Then each behaviour is
// sabotaged in memory and the suite must go red.
//
// Exit: 0 every case passed and every sabotage was caught, 1 otherwise.
'use strict'

const fs = require('node:fs')
const path = require('node:path')

const SRC = fs.readFileSync(path.resolve(__dirname, '..', 'workflows', 'review.js'), 'utf8')
const BODY = SRC.replace(/^export\s+(?=const\s+meta\b)/m, '')
const AsyncFunction = Object.getPrototypeOf(async () => {}).constructor
let body = BODY
let quiet = false

const S1 = 'plugins/p/skills/s1/SKILL.md'
const S2 = 'plugins/p/skills/s2/SKILL.md'
const FX = 'test/plugins/fixtures/'

function baseArgs(extra) {
  return {
    runStamp: 't', rubricHash: 'h', rubric: 'rubric', lint: [], handoffs: [],
    judgementIds: ['Q-X', 'Q-ROUTE-MISS', 'Q-CANN-CAPTURE'], mechanicalIds: [],
    batches: [{ key: 'p:skills', plugin: 'p', kind: 'skills', files: [S1] }],
    corpus: {
      skill: { s1: { plugin: 'p', kind: 'skill', description: 'one', path: S1 }, s2: { plugin: 'p', kind: 'skill', description: 'two', path: S2 } },
      agent: {},
    },
    fixtures: [{ name: 'fx', kind: 'skills', files: [`${FX}a.md`], cleanFiles: [], planted: [{ file: `${FX}a.md`, quoteKey: 'BAD', rule_id: 'Q-X', angle: 'procedure' }] }],
    sealed: [{ name: 'sx', kind: 'skills', files: [`${FX}b.md`], cleanFiles: [], planted: [{ file: `${FX}b.md`, quoteKey: 'BAD', rule_id: 'Q-X', angle: 'procedure' }] }],
    knownAnswers: ['k1', 'k2', 'k3', 'k4', 'k5'].map((id) => ({ id, text: `prompt ${id}`, expected: 's1', router: 'skill' }))
      .concat([{ id: 'k6', text: 'prompt k6', expected: 's2', router: 'skill' }]),
    ambiguous: [{ id: 'x1', text: 'either', router: 'skill' }],
    uncalibratedKinds: [],
    ...extra,
  }
}

// routes: promptId -> picks, identical across the three votes.
function stub(routes, opts = {}) {
  const prompts = {}
  return {
    prompts,
    answer(label, prompt) {
      prompts[label] = prompt
      if (label.startsWith('cal:')) {
        const file = label.startsWith('cal:sealed') ? `${FX}b.md` : `${FX}a.md`
        return { findings: [{ file, line: 1, quote: 'BAD', rule_id: 'Q-X', angle: 'procedure', severity: 'major', claim: 'BAD', suggested_fix: 'f', fix_tier: 'haiku' }] }
      }
      if (label.startsWith('route:')) {
        const ids = [...prompt.split('Prompts:')[1].matchAll(/"id":"([^"]+)"/g)].map((m) => m[1])
        return { routes: ids.map((id) => ({ promptId: id, picks: routes[id] || [] })) }
      }
      if (label.startsWith('judge:')) return { verdict: 'intended-handoff', rationale: 'named', winner: '' }
      if (label.startsWith('find:')) {
        if (opts.finderReportsRouteMiss && label.endsWith(':procedure')) {
          return { findings: [{ file: S1, line: 1, quote: 'q', rule_id: 'Q-ROUTE-MISS', angle: 'cannibalization', severity: 'major', claim: 'guessed', suggested_fix: 'f', fix_tier: 'human' }] }
        }
        if (opts.worseFix && label.endsWith(':procedure')) {
          return { findings: [{ file: S1, line: 3, quote: 'long description', rule_id: 'Q-X', angle: 'procedure', severity: 'minor', claim: 'c', suggested_fix: 'add triggers', fix_tier: 'haiku' }] }
        }
        return { findings: [] }
      }
      if (label.startsWith('refute:')) return { verdicts: [{ index: 0, grounded: true, ruleViolated: true, refuted: false, reason: 'real' }] }
      // Only the worseFix case marks a fix as worse. Marking every fix worse made the
      // drop case pass vacuously -- the guessed finding was declined, not dropped.
      if (label.startsWith('impact:')) return { verdicts: [{ index: 0, fixMakesWorse: !!opts.worseFix, conflictsWithRule: opts.worseFix ? 'M-DESC-LEN' : '' }] }
      if (label === 'critic') return { gaps: [] }
      if (label.startsWith('synth:')) return { plugin: 'p', verdict: 'ok', backlog: [] }
      if (label === 'cross-plugin') return 'cross'
      return null
    },
  }
}

async function execute(args, s) {
  const agent = async (prompt, o) => s.answer(o.label, prompt)
  const parallel = async (thunks) => Promise.all(thunks.map((t) => t().catch(() => null)))
  const pipeline = async (items, ...stages) => Promise.all(items.map(async (item, i) => {
    let v = item
    for (const st of stages) { try { v = await st(v, item, i) } catch { return null } }
    return v
  }))
  const fn = new AsyncFunction('args', 'agent', 'parallel', 'pipeline', 'phase', 'log', 'budget', body)
  return fn(args, agent, parallel, pipeline, () => {}, () => {}, { total: null })
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

const MEASURED = { k1: ['s1'], k2: ['s1'], k3: ['s1'], k4: ['s1'], k5: ['s2'], k6: ['s2'], x1: ['s1', 's2'] }
const UNMEASURED = { ...MEASURED, k2: ['s2'], k3: ['s2'] }

async function suite() {
  {
    const s = stub(MEASURED)
    const r = await execute(baseArgs(), s)
    const miss = r.findings.filter((f) => f.rule_id === 'Q-ROUTE-MISS')
    const cap = r.findings.filter((f) => f.rule_id === 'Q-CANN-CAPTURE')
    ok('measured run: the misroute becomes a Q-ROUTE-MISS on s1', miss.length === 1 && miss[0].file === S1 && /routes to s2/.test(miss[0].claim), r.findings)
    ok('measured run: the excused pair that captures s1 is a Q-CANN-CAPTURE', cap.length === 1 && cap[0].file === S1, r.findings)
    ok('measured run: routing is usable, nothing skipped', r.routing.routingUsable === true && r.routing.rulesSkipped.length === 0, r.routing)
    const findPrompt = Object.entries(s.prompts).find(([l]) => l.startsWith('find:'))[1]
    ok('finders receive the routing evidence, labelled MEASURED', /MEASURED routing evidence/.test(findPrompt) && /prompt k5/.test(findPrompt))
    ok('finders are never offered the code-only rules', !/Q-ROUTE-MISS|Q-CANN-CAPTURE/.test(findPrompt.split('Routing simulation')[0]))
  }
  {
    const s = stub(UNMEASURED)
    const r = await execute(baseArgs(), s)
    ok('below the floor: no Q-ROUTE-MISS, no Q-CANN-CAPTURE', !r.findings.some((f) => ['Q-ROUTE-MISS', 'Q-CANN-CAPTURE'].includes(f.rule_id)), r.findings)
    ok('below the floor: the skipped rules are named', r.routing.routingUsable === false && r.routing.rulesSkipped.includes('Q-ROUTE-MISS'), r.routing)
    const findPrompt = Object.entries(s.prompts).find(([l]) => l.startsWith('find:'))[1]
    ok('below the floor: finders are told these are HINTS ONLY', /HINTS ONLY/.test(findPrompt))
  }
  {
    const r = await execute(baseArgs(), stub(MEASURED, { finderReportsRouteMiss: true }))
    const all = [...r.findings, ...r.declined]
    ok('a finder-reported Q-ROUTE-MISS is dropped; only the measured one survives',
      all.filter((f) => f.rule_id === 'Q-ROUTE-MISS').length === 1 && !all.some((f) => f.claim === 'guessed'), all)
  }
  {
    const r = await execute(baseArgs(), stub(MEASURED, { worseFix: true }))
    ok('a fix that makes things worse is declined, not backlog',
      r.declined.length === 1 && !r.findings.some((f) => f.fixMakesWorse), { declined: r.declined, findings: r.findings })
  }
  {
    const args = baseArgs({ uncalibratedKinds: ['skills'] })
    const r = await execute(args, stub(MEASURED, { worseFix: true }))
    ok('findings from an uncalibrated kind are labelled calibrated:false',
      r.declined.every((f) => f.calibrated === false) && r.declined.length === 1, r.declined)
  }
}

const SABOTAGE = [
  ['routing findings never emitted', 'const routeFindings = !votes.measured ? [] :', 'const routeFindings = true ? [] :'],
  ['capture never checked', 'const captureFindings = !votes.measured ? [] :', 'const captureFindings = true ? [] :'],
  ['the floor ignored', 'const measured = accuracy >= ROUTING_FLOOR', 'const measured = true'],
  ['finders get no routing', " + routingBlockFor(b.files)", ''],
  ['fixMakesWorse not filtered', 'const allFindings = labelled.filter(f => !f.fixMakesWorse)', 'const allFindings = labelled'],
  ['a finder-reported code-only rule kept', "if (!CODE_ONLY.has(f.rule_id) && !seen.has(key(f))) seen.set", 'if (!seen.has(key(f))) seen.set'],
  ['code-only rules offered to finders', "const JUDGEMENT_IDS = (A.judgementIds || []).filter(id => !CODE_ONLY.has(id))", 'const JUDGEMENT_IDS = A.judgementIds || []'],
]

async function main() {
  await suite()
  console.log()
  if (failures.length) {
    console.log(`FAILED ${failures.length} of ${count}: ${failures.join(', ')}`)
    process.exit(1)
  }
  console.log(`review.js routing: ${count} assertions passed against stub hooks (no tokens spent)`)
  const uncaught = []
  quiet = true
  for (const [name, find, repl] of SABOTAGE) {
    if (!BODY.includes(find)) {
      console.log(`  FAIL sabotage '${name}': its anchor is not in review.js`)
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
