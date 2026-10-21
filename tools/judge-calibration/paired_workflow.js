export const meta = {
  name: 'andon-tribunal-paired',
  description: 'Paired measurement: the andon tribunal (four roles) against one verdict@1 contract judge, same 20 items, 5 repeats each',
  whenToUse: 'Run by hand for docs/plugin-authoring/references/judge-calibration.md. Args come from tools/judge-calibration/paired.py stage; the raw reports are read back from this run journal by paired.py.',
  phases: [
    { title: 'Tribunal', detail: 'defender and challenger blind in parallel, then verifier, then adjudicator' },
    { title: 'Contract judge', detail: 'one andon-wire@1 judge per run, decided by code' },
  ],
}

// judge-contract:start verdict@1
// verdict@1 -- the judge reports, code decides. Vendored verbatim; edit only the
// canonical copy (tools/judge-contract/verdict.inline.js) and re-vendor.
//   JUDGE_VERDICT_SCHEMA         pass as agent({ schema }) for one judge call per item
//   decideVerdict(raw, rubric, { item, decidedBy })
//                                the full verdict: outcome is "abstain" for a missing
//                                or malformed report or any rubric criterion missing,
//                                unknown or ill-typed; "fail" if any pass is false or
//                                the MINIMUM score is below rubric.threshold; else
//                                "pass". An abstain is never a pass. Throws on a
//                                malformed rubric (an author bug, not a judge result).
//   spotCheck(verdicts, k = 3)   first / middle / last by item id -- never random;
//                                return it and show it to the user every run.
const JUDGE_VERDICT_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['item', 'criteria', 'abstain', 'abstainReason'],
  properties: {
    item: { type: 'string', description: 'the id of the one item you were asked to judge, verbatim' },
    criteria: {
      type: 'array',
      description: 'one entry per rubric criterion, each id exactly once; empty only when you abstain',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['id', 'score', 'pass', 'evidence'],
        properties: {
          id: { type: 'string', description: 'a criterion id from the rubric, verbatim' },
          score: { type: 'number', minimum: 0, maximum: 1, description: '0.0 = clearly not met, 1.0 = clearly met' },
          pass: { type: 'boolean', description: 'is this criterion met' },
          evidence: { type: 'string', description: 'file:line, a quote, or command output that decided it' },
        },
      },
    },
    abstain: { type: 'boolean', description: 'true when you cannot judge this item from what you can read' },
    abstainReason: { type: ['string', 'null'], description: 'why you abstained; null when you did not' },
  },
}

function decideVerdict(raw, rubric, opts = {}) {
  const isObj = (v) => v !== null && typeof v === 'object' && !Array.isArray(v)
  const isNum = (v) => typeof v === 'number'
  const isUnit = (v) => isNum(v) && v >= 0 && v <= 1
  const rubricId = /^[a-z][a-z0-9]*(?:-[a-z0-9]+)+@(?:0|[1-9][0-9]*)$/
  const criterionId = /^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$/
  const errs = []
  if (!isObj(rubric)) errs.push('rubric is not an object')
  else {
    if (typeof rubric.id !== 'string' || !rubricId.test(rubric.id)) errs.push(`rubric id ${JSON.stringify(rubric.id)} is not <plugin>-<name>@<int>`)
    if (!isUnit(rubric.threshold)) errs.push('rubric threshold is not a number in [0, 1]')
    if (!Array.isArray(rubric.criteria) || !rubric.criteria.length) errs.push('rubric criteria is not a non-empty list')
    else {
      const seen = new Set()
      rubric.criteria.forEach((c, i) => {
        const cid = isObj(c) ? c.id : undefined
        if (typeof cid !== 'string' || !criterionId.test(cid)) errs.push(`rubric criterion ${i} has no kebab-case id`)
        else if (seen.has(cid)) errs.push(`rubric criterion ${cid} is duplicated`)
        else seen.add(cid)
        const q = isObj(c) ? c.question : undefined
        if (typeof q !== 'string' || !q.trim()) errs.push(`rubric criterion ${i} has no question`)
      })
    }
    const cal = rubric.calibration
    if (cal !== undefined && cal !== null) {
      const ok = isObj(cal) && isNum(cal.sealed) && Number.isInteger(cal.sealed) && cal.sealed >= 0 && isUnit(cal.agreement) && isUnit(cal.floor)
      if (!ok) errs.push('rubric calibration is not {sealed: int >= 0, agreement: [0,1], floor: [0,1]}')
    }
  }
  if (errs.length) throw new Error(`malformed rubric: ${errs.join('; ')}`)
  const decidedBy = opts.decidedBy === undefined ? 'judge' : opts.decidedBy
  if (decidedBy !== 'judge' && decidedBy !== 'command') throw new Error(`decidedBy must be judge or command, not ${JSON.stringify(decidedBy)}`)
  const threshold = rubric.threshold
  const firstDefect = () => {
    let item = opts.item === undefined || opts.item === null ? null : opts.item
    if (!isObj(raw)) return [item || '', 'verdict-missing', []]
    const rawItem = raw.item
    if (item === null) item = typeof rawItem === 'string' ? rawItem : ''
    if (!item) return ['', 'missing-item', []]
    if (rawItem !== item) return [item, 'item-mismatch', []]
    if (typeof raw.abstain !== 'boolean') return [item, 'malformed:abstain', []]
    if (raw.abstain) {
      const why = raw.abstainReason
      return [item, `judge:${typeof why === 'string' && why.trim() ? why.trim() : 'no reason given'}`, []]
    }
    if (!Array.isArray(raw.criteria)) return [item, 'malformed:criteria', []]
    const wanted = rubric.criteria.map((c) => c.id)
    const got = new Map()
    for (let i = 0; i < raw.criteria.length; i++) {
      const e = raw.criteria[i]
      const cid = isObj(e) ? e.id : undefined
      if (typeof cid !== 'string') return [item, `malformed-criterion:${i}`, []]
      if (got.has(cid)) return [item, `duplicate-criterion:${cid}`, []]
      if (!wanted.includes(cid)) return [item, `unknown-criterion:${cid}`, []]
      if (!isUnit(e.score)) return [item, `bad-score:${cid}`, []]
      if (typeof e.pass !== 'boolean') return [item, `bad-pass:${cid}`, []]
      if (typeof e.evidence !== 'string' || !e.evidence.trim()) return [item, `bad-evidence:${cid}`, []]
      got.set(cid, { id: cid, score: e.score, pass: e.pass, evidence: e.evidence })
    }
    for (const cid of wanted) if (!got.has(cid)) return [item, `missing-criterion:${cid}`, []]
    return [item, '', wanted.map((cid) => got.get(cid))]
  }
  const [item, reason, found] = firstDefect()
  const criteria = reason ? [] : found
  let outcome = 'abstain'
  let score = 0
  if (!reason) {
    const minScore = Math.min(...criteria.map((c) => c.score))
    score = minScore
    outcome = 'pass'
    if (minScore < threshold) outcome = 'fail'
    if (!criteria.every((c) => c.pass)) outcome = 'fail'
  }
  const cal = rubric.calibration
  return {
    item,
    rubric: rubric.id,
    decidedBy,
    criteria,
    abstain: outcome === 'abstain',
    abstainReason: reason || null,
    threshold,
    score,
    outcome,
    calibrated: isObj(cal) && cal.sealed > 0 && cal.agreement >= cal.floor,
  }
}

function spotCheck(verdicts, k = 3) {
  if (!Number.isInteger(k) || k < 0) throw new Error('k must be an integer >= 0')
  const ordered = [...verdicts].sort((a, b) => (a.item < b.item ? -1 : a.item > b.item ? 1 : 0))
  const n = ordered.length
  if (n <= k) return ordered
  if (k === 0) return []
  if (k === 1) return [ordered[0]]
  return Array.from({ length: k }, (_, i) => ordered[Math.floor((i * (n - 1)) / (k - 1))])
}
// judge-contract:end

// The tribunal roles are dispatched exactly as tribunal-protocol.md orders them. Every prompt is
// a file paired.py staged beside the run (never inside its tree), read by the agent itself, as in
// the calibration run. The verifier and adjudicator files hold their head and the contract; the
// earlier roles' reports follow them here, fenced, verbatim. No model is named: both arms
// inherit the session's model, so the comparison is between shapes, not models.
const fence = (s) => `<<<UNTRUSTED\n${s}\nUNTRUSTED>>>`
const task = (file) => `Your task is the text in the file ${file} . Read it and do exactly what it says. Reply with what it asks for and nothing else.`
const taskWith = (file, parts) => [`Your task is the text in the file ${file} , followed by the material below. Read the file and do exactly what it says. Reply with what it asks for and nothing else.`, ...parts].join('\n\n')

const items = args.items
const repeats = args.repeats

async function tribunal(it, r) {
  const dir = it.runs[`${r}a`]
  const tag = `${it.key} r${r}`
  const [d, c] = await parallel([
    () => agent(task(`${dir}/defender.txt`), { label: `defender ${tag}`, phase: 'Tribunal', agentType: 'andon:andon-defender' }),
    () => agent(task(`${dir}/challenger.txt`), { label: `challenger ${tag}`, phase: 'Tribunal', agentType: 'andon:andon-challenger' }),
  ])
  if (!d || !c) return { key: it.key, r, arm: 'a', dead: 'defender-or-challenger' }
  const v = await agent(taskWith(`${dir}/verifier-head.txt`, ["Defender's case:\n" + fence(d), "Challenger's case:\n" + fence(c)]),
    { label: `verifier ${tag}`, phase: 'Tribunal', agentType: 'andon:andon-verifier' })
  if (!v) return { key: it.key, r, arm: 'a', dead: 'verifier' }
  const a = await agent(taskWith(`${dir}/adjudicator-head.txt`,
    ["Defender's case:\n" + fence(d), "Challenger's case:\n" + fence(c), "Verifier's facts:\n" + fence(v)]),
    { label: `adjudicator ${tag}`, phase: 'Tribunal', agentType: 'andon:andon-adjudicator' })
  const m = a ? [...a.matchAll(/overall[^a-z]{0,12}(green|red|unknown)/gi)] : []
  return { key: it.key, r, arm: 'a', overall: m.length ? m[m.length - 1][1].toLowerCase() : null }
}

async function contractJudge(it, r) {
  const dir = it.runs[`${r}b`]
  const rep = await agent(task(`${dir}/judge.txt`),
    { label: `contract judge ${it.key} r${r}`, phase: 'Contract judge', agentType: 'general-purpose', schema: JUDGE_VERDICT_SCHEMA })
  if (!rep) return { key: it.key, r, arm: 'b', dead: 'judge' }
  return { key: it.key, r, arm: 'b', abstain: rep.abstain, passes: (rep.criteria || []).map((x) => x.pass) }
}

const thunks = []
for (const it of items) {
  for (let r = 1; r <= repeats; r++) {
    thunks.push(() => tribunal(it, r))
    thunks.push(() => contractJudge(it, r))
  }
}
log(`${items.length} items x ${repeats} repeats x 2 arms = ${thunks.length} runs (${items.length * repeats * 5} agent calls)`)
const runs = await parallel(thunks)
const dead = runs.filter((x) => !x || x.dead).length
log(`done: ${runs.length} runs, ${dead} dead`)
// Compact on purpose: the raw reports are read back from this run's journal by paired.py,
// so the full texts never pass through the calling conversation.
return { runs: runs.map((x, i) => x || { index: i, dead: 'thunk' }), dead }
