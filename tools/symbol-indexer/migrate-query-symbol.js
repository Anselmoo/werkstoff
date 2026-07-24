export const meta = {
  name: 'sym-migrate-query-symbol',
  description:
    'One-off cross-plugin migration: consolidate the duplicated Parallel-Safe Research Protocol text and the 6 *-query-symbol skill dirs into shared references + a plain scripts/ location.',
  whenToUse:
    'Invoked once by the sym-task-2 brief to apply and verify the symbol-index/research-protocol consolidation across all 6 plugins. No args required — plugin/file data is embedded below since this is one-off migration tooling, not a reusable capability.',
  phases: [
    { title: 'Apply', detail: 'per plugin: agent-creator does the 28 literal agent-file edits, a general-purpose agent handles moves/deletions/wiring' },
    { title: 'Verify', detail: 'per plugin: plugin-validator + skill-reviewer + a grep-based leftover check' },
  ],
}

// ---- Shared text (must match tools/symbol-indexer/parallel-safe-research-protocol.md) --
const pointerLine = plugin =>
  `\nFollow the Parallel-Safe Research Protocol at \`\${CLAUDE_PLUGIN_ROOT}/references/parallel-safe-research-protocol.md\` — this agent's \`--plugin-name\` is \`${plugin}\`.\n`

const oldBlock = plugin =>
  `\n## Parallel-Safe Research Protocol\n\nBefore broad repository discovery, read \`analysis/${plugin}/current.json\` and resolve only the matching immutable \`runs/<generation_id>/\` snapshot. Query \`symbol_index.json\` for declarations, \`file_catalog.json\` to narrow the candidate set, \`search.sqlite\` for arbitrary text, and \`artifact_manifest.json\`/\`evidence_index.json\` before repeating a report or verification command. Use \`Read\` only on exact locations returned by those artifacts.\n\nUse \`Grep\`/\`Glob\` only when FTS is unavailable, the assignment requires a regex or inline-content check, a file was generated after the snapshot, or the audit explicitly requires an exhaustive sweep. Never write, promote, or overwrite a shared analysis artifact: return structured results to the run coordinator. If assigned source edits, work in the assigned Git worktree only; do not edit the shared working tree.\n`

// ---- Per-file inline repairs — 6 of the 28 agent files also got a mid-body -----
// rewrite beyond the trailing block (2 of these lost real content). Exact
// literal find/replace pairs verified directly against `git diff` — passed
// to the apply agent so it performs mechanical substitution, not paraphrase.
const REPAIRS = {
  'andon/agents/andon-verifier.md': [
    {
      find: 'Resolve `analysis/andon/current.json` first, then use its immutable symbol, file catalog, FTS, artifact, and evidence records before running raw `grep` commands. Execute the',
      replace: 'Grep for the symbol, the handler, the schema field. Execute the',
    },
    {
      find: 'a lightweight symbol-index/grep pass is appropriate here for a quick',
      replace: 'a lightweight grep/read pass is appropriate here for a quick',
    },
  ],
  'cli-scaffold/agents/cli-scaffold-verifier.md': [
    {
      find: "never trust the generating skill's own claim that it followed the\n   doctrine.\n2. Resolve `analysis/cli-scaffold/current.json` first, then use its immutable symbol, file catalog, FTS, artifact, and evidence records before performing raw grep sweeps. If it is missing, generate it via `python3 ${CLAUDE_PLUGIN_ROOT}/skills/cli-scaffold-query-symbol/scripts/build_symbol_index.py --repo-path . --plugin-name cli-scaffold`.\n3. Check each of the five pillars",
      replace: "never trust the generating skill's own claim that it followed the\n   reference; re-derive compliance from the actual generated files.\n2. Check each of the five pillars",
    },
  ],
  'confab/agents/contract-auditor.md': [
    {
      find: '- **Research-Snapshot-First Protocol:** Resolve `analysis/confab/current.json` first, then use its immutable symbol, file catalog, FTS, artifact, and evidence records before raw `Grep` sweeps. If it is missing, generate it via `python3 ${CLAUDE_PLUGIN_ROOT}/skills/confab-query-symbol/scripts/build_symbol_index.py --repo-path . --plugin-name confab`.\n- Use Grep/Glob only when the snapshot cannot answer the target question or exhaustive coverage is explicitly required. Check more than one usage site when multiple exist, since a contract can be honored in one place and violated in another.',
      replace: '- Use Grep/Glob to locate every call site, handler, or resolver that uses the declared contract — check more than one usage site when multiple exist, since a contract can be honored in one place and violated in another.',
    },
  ],
  'cupertino/agents/handbook-drift-auditor.md': [
    {
      find: '- **Find phase.** Resolve `analysis/cupertino/current.json` first, then use its immutable symbol, file catalog, FTS, artifact, and evidence records before raw `grep` sweeps. Given the rule "every caught exception is logged with\n  the original exception object attached, never swallowed with a bare\n  `except: pass`" and a list of target files, inspect exception-handling\n  blocks in those files',
      replace: '- **Find phase.** Given the rule "every caught exception is logged with\n  the original exception object attached, never swallowed with a bare\n  `except: pass`" and a list of target files, grep for exception-handling\n  blocks in those files',
    },
  ],
  'self-assess/agents/arch-health-auditor.md': [
    {
      find: 'imports/files (`file:line` where feasible) that make it genuine. Resolve `analysis/self-assess/current.json` first and use its immutable symbol, file catalog, FTS, artifact, and evidence records before launching `grep` commands. When the code',
      replace: 'imports/files (`file:line` where feasible) that make it genuine. When the code',
    },
  ],
  'self-assess/agents/docs-drift-auditor.md': [
    {
      find: '- **Research-Snapshot-First Protocol:** Before issuing raw `Grep` or `Bash` sweeps, resolve `analysis/self-assess/current.json`. Use its immutable symbol, file catalog, FTS, artifact, and evidence records. If it is missing, generate it via `python3 ${CLAUDE_PLUGIN_ROOT}/skills/self-assess-query-symbol/scripts/build_symbol_index.py --repo-path .`.\n- Fall back to `Grep`/`Glob` only when the snapshot cannot answer the target question or requires inline regex inspection.\n- Use Read to inspect the specific line context identified by the snapshot.',
      replace: '- Use Grep/Glob to locate the corresponding implementation (function definitions, argument parsers, config loaders, route handlers, exported symbols).\n- Use Read to inspect the real signature, flag list, default values, or behavior.',
    },
  ],
}

const PLUGINS = [
  {
    name: 'self-assess',
    agentFiles: [
      'arch-health-auditor.md', 'business-rules-miner.md', 'ci-topology-auditor.md',
      'complexity-surveyor.md', 'convention-auditor.md', 'docs-drift-auditor.md',
      'idiom-auditor.md', 'idiom-remediator.md', 'stage-mapper.md',
      'transform-executor.md', 'ui-auditor.md',
    ],
    consumingSkills: [
      { skill: 'self-assess-docs-drift', workflow: 'docs-drift-scan.js' },
      { skill: 'self-assess-lint-audit', workflow: 'lint-audit-scan.js' },
      { skill: 'self-assess-arch-health', workflow: 'arch-health-scan.js' },
      { skill: 'self-assess-ci-topology', workflow: 'ci-topology-scan.js' },
    ],
    extraCleanup: true, // README line + symbol-index-scan.js
  },
  { name: 'andon', agentFiles: ['andon-adjudicator.md', 'andon-challenger.md', 'andon-defender.md', 'andon-verifier.md'], consumingSkills: [] },
  { name: 'compass', agentFiles: ['branch-proposer.md', 'instruction-candidate.md', 'reasoning-path.md'], consumingSkills: [] },
  {
    name: 'confab',
    agentFiles: ['agentic-reliability-auditor.md', 'assertion-auditor.md', 'confab-remediator.md', 'contract-auditor.md', 'dependency-auditor.md'],
    consumingSkills: [{ skill: 'confab-dependency-audit', workflow: 'dependency-audit-scan.js' }],
  },
  { name: 'cupertino', agentFiles: ['handbook-dimension-analyst.md', 'handbook-drift-auditor.md', 'handbook-remediator.md', 'handbook-verifier.md'], consumingSkills: [] },
  { name: 'cli-scaffold', agentFiles: ['cli-scaffold-verifier.md'], consumingSkills: [] },
]

const AGENT_CREATOR_SCHEMA = {
  type: 'object',
  required: ['filesEdited'],
  properties: {
    filesEdited: { type: 'array', items: { type: 'string' } },
    notes: { type: 'string' },
  },
}

const APPLY_SCHEMA = {
  type: 'object',
  required: ['plugin', 'filesChanged', 'filesDeleted'],
  properties: {
    plugin: { type: 'string' },
    filesChanged: { type: 'array', items: { type: 'string' } },
    filesDeleted: { type: 'array', items: { type: 'string' } },
    notes: { type: 'string' },
  },
}

const VERIFY_SCHEMA = {
  type: 'object',
  required: ['pass', 'issues'],
  properties: {
    pass: { type: 'boolean' },
    issues: { type: 'array', items: { type: 'string' } },
  },
}

// ---- Phase: Apply, pipelined per plugin (file-disjoint, no barrier needed) ----
log(`Applying migration across ${PLUGINS.length} plugins...`)

const applied = await parallel(
  PLUGINS.map(p => () =>
    parallel([
      // Sub-task A: the 28 agent-file edits, via plugin-dev:agent-creator (Write/Read,
      // purpose-built for authoring agent .md files).
      () => {
        const fileTasks = p.agentFiles.map(f => {
          const path = `plugins/${p.name}/agents/${f}`
          const repairs = REPAIRS[`${p.name}/agents/${f}`] || []
          const repairText = repairs.length
            ? `\nThis file ALSO needs ${repairs.length} literal inline repair(s) — a pre-existing sentence was reworded/truncated when the WIP change landed and must be restored exactly:\n` +
              repairs.map((r, i) => `  Repair ${i + 1} — replace this EXACT substring:\n  ${JSON.stringify(r.find)}\n  with this EXACT substring:\n  ${JSON.stringify(r.replace)}`).join('\n')
            : ''
          return `File: ${path}\n  Replace this EXACT substring (the trailing duplicated protocol block):\n  ${JSON.stringify(oldBlock(p.name))}\n  with this EXACT substring:\n  ${JSON.stringify(pointerLine(p.name))}${repairText}`
        }).join('\n\n')

        return agent(
          `This is a literal find-and-replace task across ${p.agentFiles.length} agent files in the "${p.name}" plugin — do not paraphrase, summarize, or touch any part of a file beyond the exact substrings named below.

For each file: Read it in full, locate the EXACT substring given, replace it with the EXACT replacement substring given (byte-for-byte, preserving all surrounding whitespace/formatting), then Write the complete file back to the same path. If a file has repair items listed, apply those too — all edits to one file happen before you Write it back once.

${fileTasks}

Return filesEdited: the list of paths you wrote.`,
          {
            agentType: 'plugin-dev:agent-creator',
            label: `agents:${p.name}`,
            phase: 'Apply',
            schema: AGENT_CREATOR_SCHEMA,
          },
        )
      },
      // Sub-task B: file moves/deletions/wiring — needs Bash+Edit, which
      // plugin-dev:agent-creator doesn't have.
      () => {
        const wiring = p.consumingSkills.length
          ? `\n\nThis plugin also has ${p.consumingSkills.length} Workflow-dispatching skill(s) that need a build-or-reuse-index step wired in:\n` +
            p.consumingSkills.map(c =>
              `- skills/${c.skill}/SKILL.md: in "Step 1 — Run the scan", immediately before its existing \`Workflow({...})\` call, insert a short paragraph: "Before dispatching, resolve or build the shared symbol-index snapshot. Read \`analysis/${p.name}/current.json\`; if missing or its source_fingerprint no longer matches, run \`python3 \"\${CLAUDE_PLUGIN_ROOT}/scripts/build_symbol_index.py\" --repo-path . --plugin-name ${p.name}\` (single-flight lock makes concurrent callers safe). For a repo well under ~50 tracked files the build overhead may not be worth it — skip this and pass symbolIndexPath: null." Then add a \`symbolIndexPath\` field to that \`Workflow({ args: {...} })\` call (the resolved snapshot dir, or null).\n` +
              `  workflows/${c.workflow}: accept an optional \`symbolIndexPath\` arg, validated the same way \`repoPath\`/other path-like args already are in this file (no backticks/newlines/traversal). Build a short conditional block, same pattern as this file's existing \`houseRulesBlock\` (or equivalent) — something like: \`const symbolIndexBlock = symbolIndexPath ? \\\`\\\\nA published symbol-index snapshot is available at \${fence(symbolIndexPath)} — prefer querying symbol_index.json/file_catalog.json/search.sqlite there over raw Grep; fall back to Grep only if the snapshot can't answer the question.\\\` : ''\` — and splice \`\${symbolIndexBlock}\` into the Find-phase \`agent(...)\` prompt template(s) only (Verify-phase referees already work off file:line citations handed to them, leave those untouched).`
            ).join('\n')
          : ''

        const cleanup = p.extraCleanup
          ? `\n\nAlso, specific to this plugin:\n- Remove the line referencing "self-assess-query-symbol" from README.md's skill list (it no longer exists).\n- Delete plugins/self-assess/workflows/symbol-index-scan.js entirely — confirmed dead code, nothing invokes it, and its job is now done by the Step-0 wiring above.`
          : ''

        return agent(
          `In the "${p.name}" plugin (repo root is the current directory), do the following file operations using Bash/git and Edit — this plugin's changes are independent of every other plugin, so don't touch anything outside plugins/${p.name}/ (or self-assess's own README.md/workflows if this is self-assess).

1. Create plugins/${p.name}/scripts/ if it doesn't exist, then \`git mv plugins/${p.name}/skills/${p.name}-query-symbol/scripts/build_symbol_index.py plugins/${p.name}/scripts/build_symbol_index.py\`.
2. \`git rm -r plugins/${p.name}/skills/${p.name}-query-symbol/\` (removes the now-empty skill dir; its only remaining contents are a gitignored __pycache__).
3. Create plugins/${p.name}/references/ if it doesn't exist yet (needed so the new tool.rrt.artifact_targets sync target has somewhere to land).${wiring}${cleanup}

Return filesChanged and filesDeleted (repo-relative paths).`,
          {
            agentType: 'general-purpose',
            label: `files:${p.name}`,
            phase: 'Apply',
            schema: APPLY_SCHEMA,
          },
        )
      },
    ]).then(([agentCreatorResult, fileOpsResult]) => ({
      plugin: p.name,
      agentCreatorResult,
      fileOpsResult,
    })),
  ),
)

log(`Apply phase done for ${applied.filter(Boolean).length}/${PLUGINS.length} plugins`)

// ---- Phase: Verify, pipelined per plugin -------------------------------------
const verified = await parallel(
  PLUGINS.map(p => () =>
    parallel([
      () =>
        agent(
          `Validate the "${p.name}" plugin at plugins/${p.name}/ still has correct structure after a migration: auto-discovery of agents/, skills/, the new scripts/, and the new references/ directory should all resolve cleanly; no orphaned references to a deleted plugins/${p.name}/skills/${p.name}-query-symbol/ path anywhere; agent frontmatter untouched. Report pass:true/false and issues:[].`,
          { agentType: 'plugin-dev:plugin-validator', label: `validate:${p.name}`, phase: 'Verify', schema: VERIFY_SCHEMA },
        ),
      () =>
        p.consumingSkills.length
          ? agent(
              `Review these ${p.consumingSkills.length} recently-edited SKILL.md file(s) for quality regressions from their Step-0 symbol-index wiring edit: ${p.consumingSkills.map(c => `plugins/${p.name}/skills/${c.skill}/SKILL.md`).join(', ')}. Confirm the new paragraph reads clearly, frontmatter is untouched, and nothing else in the file was accidentally altered. Report pass:true/false and issues:[].`,
              { agentType: 'plugin-dev:skill-reviewer', label: `review:${p.name}`, phase: 'Verify', schema: VERIFY_SCHEMA },
            )
          : Promise.resolve({ pass: true, issues: [] }),
      () =>
        agent(
          `In plugins/${p.name}/, run: \`grep -rn "query-symbol" .\` (expect zero hits) and \`grep -c "Parallel-Safe Research Protocol" agents/*.md\` (expect exactly 1 per file — the new one-line pointer, not the old 2-paragraph block; a count of 0 or 2 is a failure). Report pass:true/false and issues:[] listing any file that failed either check.`,
          { agentType: 'general-purpose', label: `leftover:${p.name}`, phase: 'Verify', schema: VERIFY_SCHEMA },
        ),
    ]).then(([validatorVerdict, skillReviewVerdict, leftoverCheck]) => ({
      plugin: p.name,
      validatorVerdict,
      skillReviewVerdict,
      leftoverCheck,
      pass: Boolean(validatorVerdict && validatorVerdict.pass && skillReviewVerdict && skillReviewVerdict.pass && leftoverCheck && leftoverCheck.pass),
    })),
  ),
)

log(`Verify phase: ${verified.filter(v => v && v.pass).length}/${PLUGINS.length} plugins passed`)

// ---- Return -------------------------------------------------------------------
// No commit happens here — the calling session runs Tier-1 static checks and
// the repo-wide leftover sweep, then presents git diff for manual review.
return {
  applied,
  verified,
  allPassed: verified.every(v => v && v.pass),
}
