export const meta = {
  name: 'quality-code-change',
  description:
    'Diff-scoped pre-commit variant of the quality plugin: fans out to whichever of the four existing domain workflows actually match the changed files, unchanged, in parallel — no ledger, no fix mode, a single one-shot pass',
  whenToUse:
    'Invoked by quality-code-change when the Workflow tool is available. Requires args {repoPath, domainArgs}, where domainArgs is a non-empty object whose keys are a subset of [dependency_audit, assertion_audit, contract_drift, agentic_reliability] and whose values are that domain\'s own workflow args, exactly as the calling skill already enumerates for the full-repo skills — only the domains with at least one matched changed file should be present. Returns per-domain results — the calling skill writes CODE_CHANGE_REVIEW.md from it.',
  phases: [{ title: 'Scan', detail: 'runs each matched domain\'s existing scan workflow, unchanged, in parallel' }],
}

const ARGS = typeof args === 'string' ? (() => { try { return JSON.parse(args) } catch (e) { return args } })() : args

const repoPath = (ARGS && ARGS.repoPath) || '.'
const domainArgs = (ARGS && ARGS.domainArgs) || {}

if (typeof repoPath !== 'string' || /[`\n\r]/.test(repoPath) || /(^|\/)\.\.(\/|$)/.test(repoPath)) {
  throw new Error(`Unsafe repoPath ${JSON.stringify(repoPath)}`)
}

const DOMAIN_WORKFLOWS = {
  dependency_audit: 'quality-dependency-audit',
  assertion_audit: 'quality-assertion-audit',
  contract_drift: 'quality-contract-drift',
  agentic_reliability: 'quality-agentic-reliability',
}
const ALL_DOMAINS = Object.keys(DOMAIN_WORKFLOWS)
const requestedDomains = Object.keys(domainArgs)

if (!requestedDomains.length) {
  throw new Error(
    'quality-code-change workflow requires a non-empty domainArgs — the calling skill should classify the changed files into domains first and only include domains with at least one matched file',
  )
}
for (const d of requestedDomains) {
  if (!ALL_DOMAINS.includes(d)) {
    throw new Error(`Unsafe domainArgs key ${JSON.stringify(d)} — must be one of ${JSON.stringify(ALL_DOMAINS)}`)
  }
}

log(`quality-code-change: ${requestedDomains.length} domain(s) matched the diff — ${requestedDomains.join(', ')}`)

const ran = await parallel(
  requestedDomains.map(domain => async () => {
    const result = await workflow(DOMAIN_WORKFLOWS[domain], domainArgs[domain])
    return { domain, result }
  }),
)

const domains = {}
let totalFindings = 0
for (const entry of ran.filter(Boolean)) {
  const { domain, result } = entry
  const findings = (result && (result.findings || result.confirmedFindings)) || []
  domains[domain] = result
  totalFindings += findings.length
}

// ---- Return -----------------------------------------------------------------
// The calling skill writes CODE_CHANGE_REVIEW.md from this — no ledger, no
// fix mode, this workflow never touches disk and runs exactly once.
return {
  repoPath,
  domainsRequested: requestedDomains,
  domains,
  stats: {
    domainsRun: requestedDomains.length,
    totalFindings,
  },
}
