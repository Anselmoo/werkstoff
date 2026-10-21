// Canonical JS side of the judge verdict contract (verdict@2). Vendor the block
// below VERBATIM into a Workflow script, above the first line that uses any of
// its three names (a `const` read before its line throws a ReferenceError):
// scripts/ci/check_judge_contract.py fails on any byte of drift, and
// tools/judge-contract/test_parity.py holds it to judge_contract.py's decide().
// Only the lines from the start marker to the end marker are compared.
// judge-contract:start verdict@2
// verdict@2 -- the judge reports, code decides. Vendored verbatim; edit only the
// canonical copy (tools/judge-contract/verdict.inline.js) and re-vendor.
//   JUDGE_VERDICT_SCHEMA         pass as agent({ schema }) for one judge call per item
//   decideVerdict(raw, rubric, { item, decidedBy })
//                                the full verdict: outcome is "abstain" for a missing
//                                or malformed report or any rubric criterion missing,
//                                unknown or ill-typed; "fail" if any DECIDED criterion
//                                has pass false or a score below rubric.threshold,
//                                whatever else is undecidable; "abstain" with reason
//                                undecidable:<ids> if nothing failed and a criterion
//                                is undecidable (score AND pass null); else "pass".
//                                An abstain is never a pass. Throws on a malformed
//                                rubric (an author bug, not a judge result).
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
          score: { type: ['number', 'null'], minimum: 0, maximum: 1, description: '0.0 = clearly not met, 1.0 = clearly met; null only together with pass null' },
          pass: { type: ['boolean', 'null'], description: 'is this criterion met; null (with score null) ONLY when no evidence available to you can decide it' },
          evidence: { type: 'string', description: 'file:line, a quote, or command output that decided it; for an undecidable criterion, what would decide it' },
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
      const undecidable = e.score === null && e.pass === null
      if (!undecidable && !isUnit(e.score)) return [item, `bad-score:${cid}`, []]
      if (!undecidable && typeof e.pass !== 'boolean') return [item, `bad-pass:${cid}`, []]
      if (typeof e.evidence !== 'string' || !e.evidence.trim()) return [item, `bad-evidence:${cid}`, []]
      got.set(cid, { id: cid, score: e.score, pass: e.pass, evidence: e.evidence })
    }
    for (const cid of wanted) if (!got.has(cid)) return [item, `missing-criterion:${cid}`, []]
    return [item, '', wanted.map((cid) => got.get(cid))]
  }
  const [item, defect, found] = firstDefect()
  const criteria = defect ? [] : found
  let reason = defect
  let outcome = 'abstain'
  let score = 0
  if (!defect) {
    const decided = criteria.filter((c) => c.pass !== null)
    const undecided = criteria.filter((c) => c.pass === null).map((c) => c.id)
    const failed = decided.some((c) => !c.pass || c.score < threshold)
    // The order of these branches IS the rule: a fail dominates an undecidable.
    if (failed) {
      outcome = 'fail'
      score = Math.min(...decided.map((c) => c.score))
    } else if (undecided.length) {
      reason = `undecidable:${undecided.join(',')}`
    } else {
      outcome = 'pass'
      score = Math.min(...decided.map((c) => c.score))
    }
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
