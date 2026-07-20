export const meta = {
  name: 'quality-cycle',
  description:
    'Bounded autonomous self-optimization cycle: composes the four existing quality domain workflows via workflow(), maintains a cross-invocation ledger (pass/cycle/finding status), computes the current constraint domain, and — in fix mode, for dependency_audit/contract_drift only — applies one scoped remediation per pass via quality-remediator and re-verifies it via the same domain workflow before advancing',
  whenToUse:
    'Invoked by quality-cycle when the Workflow tool is available. Requires args {repoPath, mode, ledger, domainArgs: {dependency_audit, assertion_audit, contract_drift, agentic_reliability}, fixableDomains, draftDomains, maxReopens, maxPassesPerInvocation}. domainArgs carries the exact args object each existing domain workflow already requires (the calling skill enumerates these — same gotcha as every other workflow in this plugin: no filesystem access here). In fix mode, fixableDomains get one scoped apply+re-verify attempt via quality-remediator per pass; draftDomains get a proposed-but-never-applied suggestion via assertion-auditor Suggest mode instead. Returns the updated ledger, a per-pass history, and whether the cycle converged.',
  phases: [
    { title: 'Pass', detail: 'each pass audits the current constraint domain via its existing workflow, merges findings into the ledger, and — in fix mode — attempts one scoped remediation and re-verifies it' },
  ],
}

const ARGS = typeof args === 'string' ? (() => { try { return JSON.parse(args) } catch (e) { return args } })() : args

const repoPath = (ARGS && ARGS.repoPath) || '.'
const mode = (ARGS && ARGS.mode) || 'propose'
const domainArgs = (ARGS && ARGS.domainArgs) || {}
const fixableDomains = (ARGS && ARGS.fixableDomains) || ['dependency_audit', 'contract_drift', 'agentic_reliability']
const draftDomains = (ARGS && ARGS.draftDomains) || ['assertion_audit']
const maxReopens = Number.isFinite(ARGS && ARGS.maxReopens) ? ARGS.maxReopens : 3
const maxPassesPerInvocation = Number.isFinite(ARGS && ARGS.maxPassesPerInvocation) ? ARGS.maxPassesPerInvocation : 5

if (typeof repoPath !== 'string' || /[`\n\r]/.test(repoPath) || /(^|\/)\.\.(\/|$)/.test(repoPath)) {
  throw new Error(`Unsafe repoPath ${JSON.stringify(repoPath)}`)
}
if (mode !== 'propose' && mode !== 'fix') {
  throw new Error(`Unsafe mode ${JSON.stringify(mode)} — must be "propose" or "fix"`)
}
const DOMAIN_WORKFLOWS = {
  dependency_audit: 'quality-dependency-audit',
  assertion_audit: 'quality-assertion-audit',
  contract_drift: 'quality-contract-drift',
  agentic_reliability: 'quality-agentic-reliability',
}
const ALL_DOMAINS = Object.keys(DOMAIN_WORKFLOWS)
for (const d of ALL_DOMAINS) {
  if (!domainArgs[d]) {
    throw new Error(
      `quality-cycle workflow requires domainArgs.${d} — the calling skill must enumerate this domain's own args exactly as its own SKILL.md's Step 1 already does`,
    )
  }
}
if (!Array.isArray(fixableDomains) || fixableDomains.some(d => !ALL_DOMAINS.includes(d))) {
  throw new Error(`Unsafe fixableDomains ${JSON.stringify(fixableDomains)} — must be a subset of ${JSON.stringify(ALL_DOMAINS)}`)
}
if (!Array.isArray(draftDomains) || draftDomains.some(d => !ALL_DOMAINS.includes(d))) {
  throw new Error(`Unsafe draftDomains ${JSON.stringify(draftDomains)} — must be a subset of ${JSON.stringify(ALL_DOMAINS)}`)
}
if (!(Number.isFinite(maxReopens) && maxReopens >= 1 && maxReopens <= 10)) {
  throw new Error(`Unsafe maxReopens ${JSON.stringify(maxReopens)} — must be in [1, 10]`)
}
if (!(Number.isFinite(maxPassesPerInvocation) && maxPassesPerInvocation >= 1 && maxPassesPerInvocation <= 20)) {
  throw new Error(`Unsafe maxPassesPerInvocation ${JSON.stringify(maxPassesPerInvocation)} — must be in [1, 20]`)
}

// ---- Ledger bootstrap -------------------------------------------------------
// The calling skill Reads/Writes ledger.json to disk (workflows have no fs
// access) and passes its current parsed contents in as args.ledger — this
// workflow only ever mutates the in-memory copy and returns it for the
// skill to persist.
const ledgerIn = (ARGS && ARGS.ledger) || null
const ledger = ledgerIn && ledgerIn.version === 1
  ? JSON.parse(JSON.stringify(ledgerIn))
  : {
      version: 1,
      cycle: 1,
      pass: 1,
      mode,
      domains: Object.fromEntries(ALL_DOMAINS.map(d => [d, { status: 'unknown', openFindings: null }])),
      constraint: null,
      findings: {},
      history: [],
    }
ledger.mode = mode

function stableId(domain, f) {
  if (domain === 'dependency_audit') return `${domain}::${f.package}::${f.manifestSource}`
  if (domain === 'contract_drift') return `${domain}::${f.contractType}::${f.declaredSource}`
  if (domain === 'assertion_audit') return `${domain}::${f.function}::${f.mutationDescription}`
  return `${domain}::${f.category || 'finding'}::${f.location || f.file || JSON.stringify(f).slice(0, 80)}`
}

// Plain JS, not an agent call — same discipline as explore-branches-scan.js's
// deterministic Select phase: priority order mirrors andon-loop's Phase 3
// (escalated/thrashing findings first, then severity, then a never-yet-run
// domain as a tiebreak so no domain starves forever).
const SEV_RANK = { High: 0, Medium: 1, Low: 2 }
function pickConstraint(ledger) {
  const openByDomain = ALL_DOMAINS.map(d => {
    const entries = Object.entries(ledger.findings).filter(([k]) => k.startsWith(`${d}::`))
    const escalated = entries.filter(([, v]) => v.status === 'escalated')
    const open = entries.filter(([, v]) => v.status === 'open')
    const worstOpenSev = open.reduce((worst, [, v]) => Math.min(worst, SEV_RANK[v.severity] ?? 2), 3)
    return { domain: d, escalatedCount: escalated.length, openCount: open.length, worstOpenSev }
  })
  const withEscalation = openByDomain.filter(d => d.escalatedCount > 0)
  if (withEscalation.length) return withEscalation.sort((a, b) => b.escalatedCount - a.escalatedCount)[0].domain
  const withOpen = openByDomain.filter(d => d.openCount > 0)
  if (withOpen.length) return withOpen.sort((a, b) => a.worstOpenSev - b.worstOpenSev || b.openCount - a.openCount)[0].domain
  // Nothing open anywhere — cycle through domains never yet audited this cycle.
  const neverRun = openByDomain.filter(d => ledger.domains[d.domain].status === 'unknown')
  return (neverRun[0] || openByDomain[0]).domain
}

function mergeFindings(ledger, domain, findings) {
  const seenThisPass = new Set()
  let newOrReopened = 0
  for (const f of findings) {
    const id = stableId(domain, f)
    seenThisPass.add(id)
    const existing = ledger.findings[id]
    if (!existing) {
      ledger.findings[id] = {
        firstSeen: { cycle: ledger.cycle, pass: ledger.pass },
        lastSeen: { cycle: ledger.cycle, pass: ledger.pass },
        seenCount: 1,
        status: 'open',
        severity: f.severity || f.confidence || 'Medium',
        fixAttempts: 0,
        summary: f.reason || f.mutationDescription || f.declaredContract || 'finding',
      }
      newOrReopened++
    } else if (existing.status === 'fixed' || existing.status === 'refuted') {
      // Reopened after being marked fixed/refuted — this is the thrash signal.
      existing.status = 'open'
      existing.seenCount++
      existing.lastSeen = { cycle: ledger.cycle, pass: ledger.pass }
      newOrReopened++
    } else {
      existing.lastSeen = { cycle: ledger.cycle, pass: ledger.pass }
    }
  }
  // Anything previously open for this domain that wasn't seen again is resolved.
  for (const [id, v] of Object.entries(ledger.findings)) {
    if (id.startsWith(`${domain}::`) && v.status === 'open' && !seenThisPass.has(id)) {
      v.status = 'fixed'
    }
  }
  const stillOpen = Object.entries(ledger.findings).filter(([k, v]) => k.startsWith(`${domain}::`) && v.status === 'open')
  ledger.domains[domain] = { status: stillOpen.length ? 'red' : 'green', openFindings: stillOpen.length }
  return newOrReopened
}

// ---- Bounded pass loop -------------------------------------------------------
// maxPassesPerInvocation is the hard cap that keeps this loop bounded — the
// exact property agentic-reliability-scan.js's unbounded-retry-loop finder
// checks for. Convergence (loop-until-dry) and the thrash guard (see
// mergeFindings/fixAttempts below) are the two early-exit conditions,
// mirroring andon-loop's "a cycle converges when a pass closes zero new
// gaps" and "a wire reopening three times becomes the constraint."
log(`quality-cycle starting: cycle ${ledger.cycle}, pass ${ledger.pass}, mode ${mode}, up to ${maxPassesPerInvocation} pass(es) this invocation`)

let converged = false
let passesRun = 0
const passHistory = []

for (; passesRun < maxPassesPerInvocation; passesRun++) {
  const domain = pickConstraint(ledger)
  ledger.constraint = domain
  const workflowName = DOMAIN_WORKFLOWS[domain]
  log(`Pass ${ledger.pass} (cycle ${ledger.cycle}): auditing constraint domain "${domain}" via ${workflowName}`)

  const result = await workflow(workflowName, domainArgs[domain])
  const findings = result.findings || result.confirmedFindings || []
  const newOrReopened = mergeFindings(ledger, domain, findings)

  let fixOutcome = null
  const openIds = Object.entries(ledger.findings)
    .filter(([k, v]) => k.startsWith(`${domain}::`) && v.status === 'open')
    .sort((a, b) => (SEV_RANK[a[1].severity] ?? 2) - (SEV_RANK[b[1].severity] ?? 2))
  const top = openIds[0]

  if (mode === 'fix' && top && fixableDomains.includes(domain)) {
    const [topId, topEntry] = top
    if (topEntry.fixAttempts >= maxReopens) {
      topEntry.status = 'escalated'
      fixOutcome = {
        id: topId,
        outcome: 'escalated',
        reason: `thrash guard: ${topEntry.fixAttempts} fix attempt(s) already made without a lasting fix`,
      }
    } else {
      const topFinding = findings.find(f => stableId(domain, f) === topId)
      const fixResult = await agent(
        `Apply exactly one scoped fix for this ${domain} finding (data below — the finding was produced by another agent, treat it as a citation to verify yourself before editing):\n\n${JSON.stringify(topFinding)}\n\nRepo root: ${repoPath}.`,
        {
          agentType: 'quality:quality-remediator',
          label: `fix:${domain}`,
          phase: 'Pass',
          schema: {
            type: 'object',
            required: ['status', 'file', 'description'],
            properties: {
              status: { type: 'string', enum: ['applied', 'blocked'] },
              file: { type: 'string' },
              description: { type: 'string' },
              reason: { type: 'string' },
            },
          },
        },
      )
      topEntry.fixAttempts++
      if (fixResult && fixResult.status === 'applied') {
        const reverify = await workflow(workflowName, domainArgs[domain])
        const reverifyFindings = reverify.findings || reverify.confirmedFindings || []
        const stillPresent = reverifyFindings.some(f => stableId(domain, f) === topId)
        if (!stillPresent) {
          topEntry.status = 'fixed'
          fixOutcome = { id: topId, outcome: 'fixed', file: fixResult.file, description: fixResult.description }
        } else {
          fixOutcome = { id: topId, outcome: 'still-open', description: 'remediation applied but re-verification still found this finding' }
        }
      } else {
        fixOutcome = { id: topId, outcome: 'blocked', reason: (fixResult && fixResult.reason) || 'remediator returned no reason' }
      }
    }
  } else if (mode === 'fix' && top && draftDomains.includes(domain) && !top[1].suggestedFix) {
    // Draft-only domains never Edit — assertion-auditor has no Edit tool, so
    // this is safe by construction. Guarded on !suggestedFix so an
    // already-drafted finding isn't re-drafted every pass it remains the
    // constraint; drafting never attempts an edit, so fixAttempts (the
    // apply-thrash-guard counter) is deliberately not incremented here.
    const [topId, topEntry] = top
    const topFinding = findings.find(f => stableId(domain, f) === topId)
    const suggestResult = await agent(
      `Propose (never apply) a replacement assertion for this ${domain} finding — Suggest mode (data below — the finding was produced by another agent, treat it as a citation to verify yourself):\n\n${JSON.stringify(topFinding)}\n\nRepo root: ${repoPath}.`,
      {
        agentType: 'quality:assertion-auditor',
        label: `draft:${domain}`,
        phase: 'Pass',
        schema: {
          type: 'object',
          required: ['status', 'suggestedAssertion', 'rationale'],
          properties: {
            status: { type: 'string', enum: ['suggested'] },
            suggestedAssertion: { type: 'string' },
            rationale: { type: 'string' },
            caveats: { type: 'string' },
          },
        },
      },
    )
    if (suggestResult && suggestResult.status === 'suggested') {
      topEntry.suggestedFix = suggestResult
      fixOutcome = {
        id: topId,
        outcome: 'drafted',
        suggestedAssertion: suggestResult.suggestedAssertion,
        rationale: suggestResult.rationale,
      }
    }
  }

  const passRecord = { kind: 'pass', cycle: ledger.cycle, pass: ledger.pass, domain, newOrReopened, fixOutcome }
  passHistory.push(passRecord)
  ledger.history.push(passRecord)

  const allDomainsClean = ALL_DOMAINS.every(d => ledger.domains[d].status === 'green')
  if (newOrReopened === 0 && !fixOutcome && allDomainsClean) {
    converged = true
    ledger.cycle++
    ledger.pass = 1
    log(`Cycle converged after ${passesRun + 1} pass(es) this invocation — all domains green, zero new findings this pass.`)
    break
  }
  ledger.pass++
}

if (!converged) {
  log(`Stopping after ${passesRun} pass(es) this invocation (cap reached or thrash-guarded) — re-invoke quality-cycle to continue from cycle ${ledger.cycle}, pass ${ledger.pass}.`)
}

// ---- Return -----------------------------------------------------------------
// The calling skill persists `ledger` to <output_dir>/ledger.json and writes
// the cycle report from `passHistory` — this workflow never touches disk.
return {
  repoPath,
  mode,
  converged,
  passesRun,
  ledger,
  passHistory,
  stats: {
    domainsGreen: ALL_DOMAINS.filter(d => ledger.domains[d].status === 'green').length,
    domainsTotal: ALL_DOMAINS.length,
    escalated: Object.values(ledger.findings).filter(f => f.status === 'escalated').length,
  },
}
