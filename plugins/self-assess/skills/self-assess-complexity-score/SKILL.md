---
name: self-assess-complexity-score
description: Computes a COCOMO/cyclomatic-complexity-style tech-debt index per module/stage of the current repo, to help prioritize which module or stage to work on first. Use this when the user asks which module needs attention first, wants a complexity/tech-debt ranking, asks to prioritize refactoring work, or wants a quantitative size/risk score per package. Pure quantitative metrics only — this never mines or proposes code, unlike self-assess-extract-rules.
---

Compute a **relative complexity/tech-debt index** per stage (or
per-language, if no stage map exists) of the current repository, to
answer "which module should we work on first" with a number instead of a
guess. This is a pure quantitative metric — no code mining, no
proposals, no adversarial verification — mirroring `code-modernization`'s
`modernize-assess --portfolio` per-system survey pattern, retargeted from
"how big/risky is this legacy system" to "which stage of this live repo
carries the most complexity."

## Step 0 — Load settings, get stage list

Read `.claude/self-assess.local.md` if it exists (see
`${CLAUDE_PLUGIN_ROOT}/references/settings.md`). If `enabled: false`, stop
and say so. Note `output_dir` (default `analysis/self-assess`). This
skill has no Verify phase, so `skip_verification` doesn't apply — don't
silently ignore it if it's set, just note in the report that it has no
effect here.

**Prefer reusing `self-assess-stage-map`'s already-solved stage
boundaries** rather than re-deriving them: `Read <output_dir>/stage_map.json`
if it exists.

- If present: for each domain node in `root.children[]`, derive
  `{name: node.name, path: <directory>}`. The `path` is the **longest
  common directory prefix** across that stage's `module` leaf children's
  `file` fields (those leaves are only the files touched by that stage's
  confirmed wires — a sample, not a full listing, per
  `self-assess-stage-map/SKILL.md` Step 3 — but the common prefix is
  still a reliable pointer to the stage's root). If a stage node has zero
  `children` (a dead-end stage with no confirmed wire), set `path: null`
  and mark that stage as a lower-confidence, name-only hint — the survey
  agent will need to glob for the stage's name instead of a known
  directory.
- If `stage_map.json` is absent: fall back to a coarser grouping — read
  `<output_dir>/preflight_summary.json`'s `languages` list if it exists,
  else detect languages directly via `${CLAUDE_PLUGIN_ROOT}/references/language-support.md`'s
  manifest-based pass (same detection `self-assess-preflight` Check 1
  uses). Build one `{name: <language>, path: null}` entry per detected
  language.

State plainly in the eventual report whether stage-map-derived or
language-fallback scope was used — this materially affects how precise
the "module" in the report actually is.

## Step 1 — Run the scan

**Preferred — Workflow orchestration.** If the **Workflow tool** is
available in this session (this skill invocation is your authorization):

```
Workflow({
  scriptPath: "${CLAUDE_PLUGIN_ROOT}/workflows/complexity-score-scan.js",
  args: { repoPath: "<repo root, usually '.'>", stages: [{name, path}, ...] }
})
```

One survey agent runs per stage, all independent (no Verify phase — a
complexity number isn't a factual claim that can be "wrong" the way a
docs-drift contradiction is; same "informational" treatment
`self-assess-ci-topology` gives non-actionable findings). The complexity
index itself is computed **by the workflow**, not by any agent, so every
row uses the identical formula.

**Fallback** (no Workflow tool) — spawn one **complexity-surveyor**
subagent per stage directly, with the same brief the workflow gives its
survey agents (see `workflows/complexity-score-scan.js`'s prompt if you
need to reconstruct it). Then compute the complexity index yourself in
this turn, using the exact same formula as the workflow —
`2.94 × (KSLOC)^1.10` — so the fallback and Workflow paths always agree.

## Step 2 — Write the report

Create `<output_dir>/COMPLEXITY_SCORE.md`:
- A table, ranked by Complexity Index descending: **Stage/Module ·
  Language · SLOC · Files · Mean CCN · Max CCN · Complexity Index ·
  Priority** (Priority is just a plain-English rank label — 1st/2nd/3rd
  highest, not a P0/P1/P2 category the way extract-rules uses it).
- A footnote carrying the workflow's `complexityIndexFormula` caveat
  **verbatim**: this is a RELATIVE ranking index, NOT a duration or cost
  estimate — never render it as person-months/weeks/dates.
- 2-3 sentences naming the highest-index stage and why it's worth
  looking at first.
- List any `unmeasured` stages plainly (agent skipped or errored) —
  never synthesize placeholder numbers for them.

Also write `<output_dir>/complexity_score_summary.json`:
```json
{"stagesScored": N, "totalSloc": N, "topComplexityStage": "<name>", "complexityByStage": {"<stage>": <index>, ...}, "unmeasured": [<stage names that failed>]}
```

## Present

Report: the highest-index stage first, which tool produced the numbers
(`metricsTool`, for reproducibility), unmeasured count if any, and
whether stage-map-derived or language-fallback scope was used. Suggest:
`glow -p <output_dir>/COMPLEXITY_SCORE.md`
