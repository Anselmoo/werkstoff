#!/usr/bin/env node
// handbook-fix.js must apply only findings whose independent re-verification said "confirmed".
//
// usage: node plugins/cupertino/scripts/test_fail_closed.js
//
// `isConfirmed` once read `!f.verification || ...`, so a finding with NO verification
// counted as confirmed -- the gate passed exactly the findings nobody had verified. This
// evaluates the workflow body the way the runtime does (export stripped, body compiled as
// an async function with the hooks as parameters) against stub hooks, then sabotages itself:
// the old fail-open line is planted back in memory and the suite must go red.
//
// Exit: 0 every case passed and the sabotage was caught, 1 otherwise.
'use strict'

const fs = require('node:fs')
const path = require('node:path')

const SRC = fs.readFileSync(path.resolve(__dirname, '..', 'workflows', 'handbook-fix.js'), 'utf8')
const AsyncFunction = Object.getPrototypeOf(async () => {}).constructor
const strip = (src) => src.replace(/^export\s+(?=const\s+meta\b)/m, '')

const finding = (over) => ({ rule: 'no-inline-styles', file: 'src/a.tsx', line: 7, title: 't', evidence: 'e', suggestedFix: 'f', mechanical: true, ...over })

// Runs the workflow body; reports what it returned and which agents it dispatched.
async function run(src, findings) {
  const calls = []
  const agent = async (_prompt, opts) => {
    calls.push(opts.label)
    if (opts.label.startsWith('remediate:')) return { results: [{ file: 'src/a.tsx', line: 7, status: 'applied', change: 'c' }] }
    return { location: 'src/a.tsx:7', compliant: true, note: 'n' }
  }
  const parallel = async (thunks) => Promise.all(thunks.map((t) => t().catch(() => null)))
  const pipeline = async (items, first, second) => Promise.all(items.map(async (it) => second(await first(it), it)))
  const fn = new AsyncFunction('args', 'agent', 'parallel', 'pipeline', 'phase', 'log', strip(src))
  const result = await fn({ findings }, agent, parallel, pipeline, () => {}, () => {})
  return { result, calls }
}

// Each is a mechanical finding whose verification is NOT a "confirmed" object.
const NOT_CONFIRMED = [
  ['verification absent', finding({})],
  ['verification null', finding({ verification: null })],
  ['verification true', finding({ verification: true })],
  ['verification the string "confirmed"', finding({ verification: 'confirmed' })],
  ['verification empty object', finding({ verification: {} })],
  ['verdict false_positive', finding({ verification: { verdict: 'false_positive' } })],
  ['verdict boolean true', finding({ verification: { verdict: true } })],
]

async function suite(src) {
  const failures = []
  for (const [name, f] of NOT_CONFIRMED) {
    const { result, calls } = await run(src, [f])
    if (calls.length !== 0 || result.clusters.length !== 0 || result.skipped !== 1) failures.push(`${name}: dispatched ${JSON.stringify(calls)}, returned ${JSON.stringify(result)}`)
  }
  // Positive control: without it, an isConfirmed that is always false would pass every case above.
  const ctl = await run(src, [finding({ verification: { verdict: 'confirmed' } })])
  if (!ctl.calls.some((l) => l.startsWith('remediate:')) || ctl.result.clusters.length !== 1) failures.push(`positive control: a confirmed finding was not remediated: ${JSON.stringify(ctl)}`)
  // The gate is per finding: one unconfirmed finding must not ride along with a confirmed one.
  const mix = await run(src, [finding({ verification: { verdict: 'confirmed' } }), finding({ line: 9 })])
  if (mix.result.skipped !== 1 || mix.calls.filter((l) => l.startsWith('verify:')).length !== 1) failures.push(`mixed batch: ${JSON.stringify(mix)}`)
  return failures
}

const SABOTAGE = {
  anchor: 'f != null && typeof f.verification === "object" && f.verification !== null && f.verification.verdict === "confirmed"',
  failOpen: '!f.verification || f.verification.verdict === "confirmed"',
}

;(async () => {
  const failures = await suite(SRC)
  for (const f of failures) console.log(`  FAIL ${f}`)
  console.log(failures.length ? `${failures.length} case(s) failed` : `  ok   ${NOT_CONFIRMED.length} unconfirmed shapes dropped, positive control and mixed batch hold`)

  let caught = false
  if (!SRC.includes(SABOTAGE.anchor)) {
    console.log('  FAIL sabotage anchor not found in handbook-fix.js -- it would plant nothing and pass vacuously')
  } else {
    caught = (await suite(SRC.replace(SABOTAGE.anchor, SABOTAGE.failOpen))).length > 0
    console.log(`  ${caught ? 'ok  ' : 'FAIL'} sabotage: fail-open isConfirmed ${caught ? 'was caught' : 'was NOT caught'}`)
  }
  process.exit(failures.length === 0 && caught ? 0 : 1)
})().catch((e) => {
  console.error(e)
  process.exit(1)
})
