export const meta = {
  name: 'confab-cycle',
  description:
    'Bounded autonomous self-optimization cycle: composes the four existing confab domain workflows via workflow(), maintains a cross-invocation ledger (pass/cycle/finding status), computes the current constraint domain, and — in fix mode, for dependency_audit/contract_drift only — applies one scoped remediation per pass via confab-remediator and re-verifies it via the same domain workflow before advancing',
  whenToUse:
    'Invoked by confab-cycle when the Workflow tool is available. Requires args {repoPath, mode, ledger, domainArgs: {dependency_audit, assertion_audit, contract_drift, agentic_reliability}, fixableDomains, draftDomains, maxReopens, maxPassesPerInvocation, symbolGraphSnippets?}. domainArgs carries the exact args object each existing domain workflow already requires (the calling skill enumerates these — same gotcha as every other workflow in this plugin: no filesystem access here). symbolGraphSnippets (default {}) maps a finding\'s own stableId to an advisory "possibly related" note the calling skill already resolved from build_symbol_index.py\'s same-file symbol-graph, for dependency_audit/contract_drift findings the loaded ledger already knew about — never required, never blocks a dispatch when absent. In fix mode, fixableDomains get one scoped apply+re-verify attempt via confab-remediator per pass; draftDomains get a proposed-but-never-applied suggestion via assertion-auditor Suggest mode instead. Returns the updated ledger, a per-pass history, and whether the cycle converged.',
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
// symbolGraphSnippets, if supplied, maps the finding's own stableId(domain, f)
// -> a plain-text "possibly related" note the calling skill already resolved
// by reading the nearest symbol-graph entry for that finding's (file, line)
// (this workflow has no filesystem access, so the calling confab-cycle/SKILL.md
// does the Read/Glob work and passes the resolved text in). Absent or missing
// entries are the normal, expected case, never an error.
const symbolGraphSnippets = (ARGS && ARGS.symbolGraphSnippets) || {}

if (typeof repoPath !== 'string' || /[`\n\r]/.test(repoPath) || /(^|\/)\.\.(\/|$)/.test(repoPath)) {
  throw new Error(`Unsafe repoPath ${JSON.stringify(repoPath)}`)
}
if (mode !== 'propose' && mode !== 'fix') {
  throw new Error(`Unsafe mode ${JSON.stringify(mode)} — must be "propose" or "fix"`)
}
const DOMAIN_WORKFLOWS = {
  dependency_audit: 'confab-dependency-audit',
  assertion_audit: 'confab-assertion-audit',
  contract_drift: 'confab-contract-drift',
  agentic_reliability: 'confab-agentic-reliability',
}
const ALL_DOMAINS = Object.keys(DOMAIN_WORKFLOWS)
for (const d of ALL_DOMAINS) {
  if (!domainArgs[d]) {
    throw new Error(
      `confab-cycle workflow requires domainArgs.${d} — the calling skill must enumerate this domain's own args exactly as its own SKILL.md's Step 1 already does`,
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
log(`confab-cycle starting: cycle ${ledger.cycle}, pass ${ledger.pass}, mode ${mode}, up to ${maxPassesPerInvocation} pass(es) this invocation`)

let converged = false
let passesRun = 0
const passHistory = []

// Cluster key: findings that would land in the same file, fixed by the
// same kind of edit, batch into one remediator dispatch instead of one
// dispatch per finding. Only dependency_audit and contract_drift have a
// verified, stable per-file grouping rule; agentic_reliability findings
// (excessive-tool-grant) keep singleton dispatch — their finding shape
// wasn't part of this pass's grounding and clustering an unverified
// shape risks silently mis-grouping unrelated tool-grant fixes.
function clusterKey(domain, f) {
  if (domain === 'dependency_audit') return f.manifestSource
  if (domain === 'contract_drift') return `${String(f.declaredSource).replace(/:\d+$/, '')}::${f.contractType}`
  return null
}

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
      const topKey = topFinding && clusterKey(domain, topFinding)
      // cluster[0] is always `top` itself — filter preserves openIds' order,
      // and top trivially matches its own key — so downstream code can keep
      // treating cluster[0]'s outcome as "the" fixOutcome for compatibility.
      const cluster = topKey
        ? openIds.filter(([id, entry]) => {
            if (id === topId) return true
            if (entry.fixAttempts >= maxReopens) return false
            const f = findings.find(ff => stableId(domain, ff) === id)
            return f && clusterKey(domain, f) === topKey
          })
        : [top]
      const clusterFindings = cluster.map(([id]) => findings.find(f => stableId(domain, f) === id)).filter(Boolean)

      const possiblyRelated = clusterFindings
        .map(f => symbolGraphSnippets[stableId(domain, f)])
        .filter(Boolean)

      const fixResult = await agent(
        `Apply exactly one scoped fix for EACH of these ${clusterFindings.length} ${domain} finding(s) — they were pre-clustered because they share ${domain === 'dependency_audit' ? 'the same manifest file' : 'the same file and contract type'}; fix each independently and report one result per finding, in the same order given (data below — findings were produced by another agent, treat each as a citation to verify yourself before editing):\n\n${JSON.stringify(clusterFindings)}${possiblyRelated.length ? `\n\nPossibly related same-file symbols (advisory — double-check before editing, do not assume independence): ${JSON.stringify(possiblyRelated)}` : ''}\n\nRepo root: ${repoPath}.`,
        {
          agentType: 'confab:confab-remediator',
          label: `fix:${domain}`,
          phase: 'Pass',
          schema: {
            type: 'object',
            required: ['results'],
            properties: {
              results: {
                type: 'array',
                items: {
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
            },
          },
        },
      )
      const results = (fixResult && fixResult.results) || []
      for (const [, entry] of cluster) entry.fixAttempts++

      const anyApplied = results.some(r => r && r.status === 'applied')
      const reverify = anyApplied ? await workflow(workflowName, domainArgs[domain]) : null
      const reverifyFindings = reverify ? (reverify.findings || reverify.confirmedFindings || []) : []

      const clusterOutcomes = cluster.map(([id, entry], i) => {
        const r = results[i]
        if (!r || r.status !== 'applied') {
          return { id, outcome: 'blocked', reason: (r && r.reason) || 'remediator returned no reason' }
        }
        const stillPresent = reverifyFindings.some(f => stableId(domain, f) === id)
        if (!stillPresent) {
          entry.status = 'fixed'
          return { id, outcome: 'fixed', file: r.file, description: r.description }
        }
        return { id, outcome: 'still-open', description: 'remediation applied but re-verification still found this finding' }
      })
      fixOutcome = { ...clusterOutcomes[0], clusterSize: clusterOutcomes.length, clusterOutcomes }
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
        agentType: 'confab:assertion-auditor',
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
  log(`Stopping after ${passesRun} pass(es) this invocation (cap reached or thrash-guarded) — re-invoke confab-cycle to continue from cycle ${ledger.cycle}, pass ${ledger.pass}.`)
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
