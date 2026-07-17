---
name: quality-cycle
description: This skill should be used when the user asks to "run a quality self-optimization cycle", "harden the quality findings", "fix what quality found and re-check", "converge the quality audit", or wants the quality plugin's four domain audits run repeatedly with cross-run memory until they stop finding new things — optionally applying and re-verifying fixes for dependency-hallucination, contract-drift, and mechanical agentic-reliability findings, and drafting (never applying) assertion-strength suggestions.
---

Run a bounded, autonomous self-optimization cycle across the `quality`
plugin's four domain audits (`quality-dependency-audit`,
`quality-assertion-audit`, `quality-contract-drift`,
`quality-agentic-reliability`), reusing each one's existing Find→Verify
workflow unchanged. This adds three things none of the four domain skills
has on its own: a persistent ledger so a recurring finding is recognized as
recurring (not re-reported as new every time), a `propose`/`fix` mode
switch with a three-way split in `fix` mode — `cycle.fixable_domains`
(default `dependency_audit`, `contract_drift`, and `agentic_reliability`'s
`excessive-tool-grant` category only) get one scoped remediation attempt
plus a re-verify via `quality-remediator`; `cycle.draft_domains` (default
`assertion_audit`) get a proposed-but-never-applied suggestion via
`assertion-auditor`'s Suggest mode instead, since a generated assertion has
no ground truth beyond the module's current — possibly buggy — runtime
behavior; everything else is report-only — and a thrash guard (a finding
that keeps reopening after `cycle.max_reopens` *applied* fix attempts gets
escalated instead of retried forever; drafted suggestions never count
against this guard, since drafting never attempts an edit).

## Step 0 — Load settings and the ledger

Read `.claude/quality.local.md` if it exists (see
`${CLAUDE_PLUGIN_ROOT}/references/settings.md`). If `enabled: false`, stop
and say so. Note `output_dir` (default `analysis/quality`) and the `cycle`
block: `mode` (default `propose`), `fixable_domains` (default
`[dependency_audit, contract_drift, agentic_reliability]` — for
`agentic_reliability`, `quality-remediator` itself only ever acts on the
`excessive-tool-grant` category, everything else in that domain always
comes back `blocked`), `draft_domains` (default `[assertion_audit]` —
proposed, never applied), `max_reopens` (default `3`),
`max_passes_per_invocation` (default `5`).

Read `<output_dir>/ledger.json` if it exists and parse it; otherwise this
is cycle 1, pass 1 — the workflow initializes a fresh ledger itself when
none is supplied.

**If `cycle.mode` resolves to `fix`:** before doing anything else, check
the target repo's git status (`git status --porcelain`). If it is not
clean, tell the user plainly that fix mode is about to edit tracked files
and ask them to confirm proceeding on a dirty tree, or to commit/stash
first, or to switch to a branch — do not proceed silently. This mirrors
this repo's own guidance on pausing before hard-to-reverse actions; a code
edit is git-reversible, but the user should know it's about to happen
before it does.

## Step 1 — Enumerate inputs for all four domains

The workflow script has no filesystem access, so gather every domain's
`args` object yourself, exactly as that domain's own skill already does in
its own Step 0/Step 1 — do not reinvent the enumeration logic, reuse it:

- `dependency_audit`: Glob for manifest files per
  `quality-dependency-audit/SKILL.md` Step 0 (`package.json` → npm,
  `requirements.txt`/`pyproject.toml` → pip, `Cargo.toml` → cargo,
  `go.mod` → go, `Gemfile` → gem), build `manifestFiles: [{path, type}]`.
- `assertion_audit`: enumerate `targetFiles`/`testFiles` per
  `quality-assertion-audit/SKILL.md` Step 0/1 (honor a user-named target;
  otherwise prefer recently-changed files over a full-repo sweep) and
  check `<output_dir>/preflight_summary.json` for a `mutationTool` to pass.
- `contract_drift`: Glob for contract sources (typed source files, schema
  files) and load house rules per `quality-contract-drift/SKILL.md` Step 0.
- `agentic_reliability`: enumerate `skillFiles`/`agentFiles`/`workflowFiles`
  (`**/skills/*/SKILL.md`, `**/agents/*.md`, `**/workflows/*.js`) per
  `quality-agentic-reliability/SKILL.md` Step 0.

Assemble `domainArgs: {dependency_audit, assertion_audit, contract_drift,
agentic_reliability}`, one complete args object per domain, matching each
domain workflow's own documented `args` shape exactly (including that
domain's own `skipVerification` setting where it has one — `assertion_audit`
has none, per its own SKILL.md).

If a domain has genuinely nothing to enumerate (e.g. no manifest files
exist at all), still build its `args` object with empty arrays rather than
omitting the domain — `quality-cycle-scan.js` requires all four
`domainArgs` entries to be present, and a domain workflow with an empty
input list reports "nothing to check" for itself, which is a legitimate
green status, not an error.

## Step 2 — Run the cycle

**Preferred — Workflow orchestration.** If the **Workflow tool** is
available in this session (this skill invocation is your authorization):

```
Workflow({
  scriptPath: "${CLAUDE_PLUGIN_ROOT}/workflows/quality-cycle-scan.js",
  args: {
    repoPath: "<repo root, usually '.'>",
    mode: <cycle.mode from settings, default "propose">,
    ledger: <parsed ledger.json contents, or null if none exists>,
    domainArgs: <assembled in Step 1>,
    fixableDomains: <cycle.fixable_domains from settings>,
    draftDomains: <cycle.draft_domains from settings>,
    maxReopens: <cycle.max_reopens from settings, default 3>,
    maxPassesPerInvocation: <cycle.max_passes_per_invocation from settings, default 5>
  }
})
```

It runs up to `maxPassesPerInvocation` passes, each auditing whichever
domain is currently the "constraint" (the domain with the most/worst open
or escalated findings) via that domain's own existing workflow, merging
results into the ledger. In `fix` mode, for domains in `fixable_domains`,
it applies one scoped fix per pass via `quality-remediator` and re-runs
that domain's workflow to confirm the fix held before marking the finding
resolved; for domains in `draft_domains`, it instead asks
`assertion-auditor`'s Suggest mode for a proposed-but-unapplied fix
(stored on the ledger entry, never re-drafted once proposed) — every other
domain is report-only in this pass. It stops early either on convergence
(a pass that closes zero new/reopened findings across all four domains and
produces no fix/draft outcome) or when it hits the pass cap — never spins
indefinitely.

**Fallback** (no Workflow tool) — run each of the four domain skills'
existing fallback path once per pass (their own SKILL.md Step 1 fallback),
in the constraint order you compute yourself by the same rule the workflow
uses (escalated findings' domain first, else most open High-severity
findings, else most total open findings, else a never-yet-run domain), and
apply the same ledger-merge/thrash-guard/fix-vs-draft bookkeeping described
in `quality-cycle-scan.js` inline in this skill rather than in a script —
for a constraint domain in `draft_domains`, spawn an **assertion-auditor**
subagent in Suggest mode directly rather than `quality-remediator` (no
`Edit` involved either way). Cap yourself at the same
`maxPassesPerInvocation`.

## Step 3 — Persist the ledger and write the cycle report

Write the workflow's returned `ledger` back to `<output_dir>/ledger.json`
(pretty-printed JSON) — this is what makes the next invocation resumable.

Create/update `<output_dir>/QUALITY_CYCLE.md`:
- **Cycle status** — cycle #, pass #, mode, whether this invocation
  converged, passes run this invocation
- **Per-domain status** — green/red/unknown, open finding count
- **This invocation's passes** — one entry per pass: constraint domain,
  new/reopened count, fix outcome if any (`fixed` / `still-open` /
  `blocked` / `escalated` / `drafted`, with the reason for
  blocked/escalated or the suggestion for drafted)
- **Escalated findings** — a dedicated section for anything the thrash
  guard escalated (fix attempted `max_reopens` times without holding) —
  this is the list most worth a human's attention first
- If not converged, name the constraint domain and suggest re-running
  `quality-cycle` to continue

## Present

Report: cycle/pass number, mode, converged or not, and — if `fix` mode
ran — a breakdown of what happened this invocation: N fix(es) applied
(file + description, so the user can review the diff before committing
anything themselves — this skill never commits or pushes), M
suggestion(s) drafted for human review (domain + rationale, never
applied), and P blocked/escalated. If the constraint domain isn't in
either `fixable_domains` or `draft_domains`, say so and name the single
next-most-useful step, same spirit as `quality-status`'s verdict line.
Suggest: `glow -p <output_dir>/QUALITY_CYCLE.md`
