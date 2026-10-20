#!/usr/bin/env node
// verify.js must map the blind judge's outcome onto the module verdict:
//   pass -> PASS; fail with no-behavior-change failed -> FAIL; any other fail or an
//   abstain (a dead judge included) -> PASS-WITH-GAPS. An abstain is never a PASS.
//
// usage: node plugins/passung/scripts/test_verify_mapping.js
//
// Evaluates the workflow body the way the runtime does (export stripped, body compiled as
// an async function with the hooks as parameters) against stub agents, then sabotages
// itself: the line that turns a failed no-behavior-change into FAIL is planted back to the
// old "any fail is PASS-WITH-GAPS" behaviour and the suite must go red.
//
// Judge verdicts are paired with PASS modules by position, and duplicate units[].name is
// refused in args validation (#119): a by-name Map let a later verdict overwrite an earlier
// one and hid a behaviour change. Under unique names the two pairings agree, so the
// duplicate-name refusal is what the by-name revert is caught by; the positional pairing is
// caught separately by planting a mispairing.
//
// Exit: 0 every case passed and the sabotage was caught, 1 otherwise.
'use strict'

const fs = require('node:fs')
const path = require('node:path')

const SRC = fs.readFileSync(path.resolve(__dirname, '..', 'workflows', 'verify.js'), 'utf8')
const AsyncFunction = Object.getPrototypeOf(async () => {}).constructor
const strip = (src) => src.replace(/^export\s+(?=const\s+meta\b)/m, '')

const IDS = ['changed-branches-covered', 'docs-current', 'tests-exercise-change', 'no-behavior-change']
const crit = (over) => IDS.map((id) => ({ id, score: 1, pass: true, evidence: `${id}: verified`, ...(over[id] || {}) }))
const report = (over) => ({ item: 'mod', criteria: crit(over), abstain: false, abstainReason: null })

// Runs the workflow with the given modules; each module's Check verdict is PASS and its judge
// behaviour comes from `judges[name]`. Returns the verdicts by unit name.
async function runUnits(src, units, judges) {
  const agent = async (prompt, opts) => {
    const name = opts.label.slice(opts.label.indexOf(':') + 1)
    if (opts.phase === 'Check') return { unit: name, verdict: 'PASS', reason: 'tests pass' }
    const judge = judges[name]
    if (judge === 'throw') throw new Error('judge died')
    return judge
  }
  const parallel = async (thunks) => Promise.all(thunks.map((t) => t().catch(() => null)))
  const fn = new AsyncFunction('args', 'agent', 'parallel', 'pipeline', 'phase', 'log', strip(src))
  const result = await fn({ area: 'a', dimension: 'd', units }, agent, parallel, null, () => {}, () => {})
  return Object.fromEntries(result.results.map((r) => [r.unit, r.verdict]))
}

async function run(src, judge) {
  return (await runUnits(src, [{ name: 'mod', path: 'src/mod' }], { mod: judge })).mod
}

const CASES = [
  ['all criteria pass', report({}), 'PASS'],
  ['no-behavior-change fails', report({ 'no-behavior-change': { pass: false, score: 0.1 } }), 'FAIL'],
  ['no-behavior-change scores under threshold', report({ 'no-behavior-change': { pass: true, score: 0.4 } }), 'FAIL'],
  ['docs-current fails only', report({ 'docs-current': { pass: false, score: 0.2 } }), 'PASS-WITH-GAPS'],
  ['tests-exercise-change fails only', report({ 'tests-exercise-change': { pass: false, score: 0.2 } }), 'PASS-WITH-GAPS'],
  ['judge abstains', { item: 'mod', criteria: [], abstain: true, abstainReason: 'cannot run tests' }, 'PASS-WITH-GAPS'],
  ['judge returns nothing', null, 'PASS-WITH-GAPS'],
  ['judge throws', 'throw', 'PASS-WITH-GAPS'],
  ['judge omits no-behavior-change', { item: 'mod', criteria: crit({}).slice(0, 3), abstain: false, abstainReason: null }, 'PASS-WITH-GAPS'],
]

const rep = (item, over) => ({ ...report(over), item })
const TWO = [{ name: 'one', path: 'src/one' }, { name: 'two', path: 'src/two' }]

async function suite(src) {
  const failures = []
  for (const [name, judge, want] of CASES) {
    const got = await run(src, judge)
    if (got !== want) failures.push(`${name}: want ${want}, got ${got}`)
  }
  // Two distinct modules: the first changes behaviour, the second is clean. Each verdict must
  // land on its own module, not leak onto the other.
  const two = await runUnits(src, TWO, { one: rep('one', { 'no-behavior-change': { pass: false, score: 0.1 } }), two: rep('two', {}) })
  if (two.one !== 'FAIL' || two.two !== 'PASS') failures.push(`two units, first changed behaviour: want one=FAIL two=PASS, got one=${two.one} two=${two.two}`)
  // And the mirror image, so a fixed-index or first-wins pairing cannot satisfy both.
  const mirror = await runUnits(src, TWO, { one: rep('one', {}), two: rep('two', { 'no-behavior-change': { pass: false, score: 0.1 } }) })
  if (mirror.one !== 'PASS' || mirror.two !== 'FAIL') failures.push(`two units, second changed behaviour: want one=PASS two=FAIL, got one=${mirror.one} two=${mirror.two}`)
  // A verdict echoing the wrong item must abstain, never pass for the other module.
  const swapped = await runUnits(src, TWO, { one: rep('two', {}), two: rep('two', {}) })
  if (swapped.one !== 'PASS-WITH-GAPS' || swapped.two !== 'PASS') failures.push(`item mismatch: want one=PASS-WITH-GAPS two=PASS, got one=${swapped.one} two=${swapped.two}`)
  // Duplicate units[].name is refused before any dispatch.
  let refused = null
  try {
    await runUnits(src, [{ name: 'dup', path: 'src/a' }, { name: 'dup', path: 'src/b' }], { dup: rep('dup', {}) })
  } catch (e) {
    refused = e.message
  }
  if (!refused || !/Duplicate unit name/.test(refused)) failures.push(`duplicate units[].name: want a refusal, got ${refused === null ? 'a normal run' : refused}`)
  return failures
}

const SABOTAGES = [
  {
    name: 'a failed no-behavior-change kept as PASS-WITH-GAPS',
    edits: [["const behaviorChanged = v.outcome === 'fail' && failing.some(c => c.id === BEHAVIOR_CRITERION)", 'const behaviorChanged = false']],
  },
  {
    name: 'duplicate units[].name accepted',
    edits: [["if (seenUnitNames.has(name)) throw", 'if (false) throw']],
  },
  {
    name: 'judge verdicts paired by position replaced with a fixed index',
    edits: [['const v = judged[i] ||', 'const v = judged[0] ||']],
  },
  {
    name: 'pre-#119 by-name pairing and no duplicate-name guard',
    edits: [
      ["if (seenUnitNames.has(name)) throw", 'if (false) throw'],
      ['const judgeVerdicts = []', 'const verdictByUnit = new Map(judged.filter(Boolean).map(v => [v.item, v]))\nconst judgeVerdicts = []'],
      ['const v = judged[i] ||', 'const v = verdictByUnit.get(r.unit) ||'],
    ],
  },
]

;(async () => {
  const failures = await suite(SRC)
  for (const f of failures) console.log(`  FAIL ${f}`)
  console.log(failures.length ? `${failures.length} case(s) failed` : `  ok   ${CASES.length + 4} judge outcomes and pairings map to the right module verdict`)

  let allCaught = true
  for (const sab of SABOTAGES) {
    const missing = sab.edits.filter(([anchor]) => !SRC.includes(anchor))
    if (missing.length) {
      console.log(`  FAIL sabotage "${sab.name}": anchor not found in verify.js -- it would plant nothing and pass vacuously`)
      allCaught = false
      continue
    }
    const planted = sab.edits.reduce((acc, [anchor, bad]) => acc.replace(anchor, bad), SRC)
    const caught = (await suite(planted)).length > 0
    allCaught = allCaught && caught
    console.log(`  ${caught ? 'ok  ' : 'FAIL'} sabotage: ${sab.name} ${caught ? 'was caught' : 'was NOT caught'}`)
  }
  process.exit(failures.length === 0 && allCaught ? 0 : 1)
})()
