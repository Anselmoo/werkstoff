---
name: cupertino-handbook-check
description: Compares new or changed work in one domain -- design, code, testing, documentation -- against that domain's existing handbook artifact (see cupertino-handbook-draft) and flags concrete divergence with file:line evidence. Use when the user asks to check code/design/tests/docs against the handbook, verify new work follows our conventions, or find drift from the handbook. Fully self-contained, using its own Workflow-orchestrated Find-then-adversarial-Verify pass -- never invokes self-assess or andon skills even when installed. Stops and suggests cupertino-handbook-draft first if no handbook exists yet for the resolved domain. Its output feeds cupertino-handbook-fix, which applies a gated subset of what this skill finds.
---

Compare new or changed work in one domain against that domain's existing
handbook artifact, flagging concrete divergence with `file:line` evidence
— the third stage of `cupertino`'s handbook lifecycle (`draft` → `apply` →
`check` → `fix`). See `${CLAUDE_PLUGIN_ROOT}/references/handbook.md` for the
shared vocabulary and domain-resolution rule every lifecycle skill uses.

Fully self-contained: this skill never invokes `self-assess` or `andon`
skills, agents, or workflows.

## Step 0 — Load settings and resolve domain

Read `.claude/cupertino.local.md` if it exists (see
`${CLAUDE_PLUGIN_ROOT}/references/handbook-settings.md`). If `enabled:
false`, stop and say so. Note `handbook.output_dir` (default
`docs/cupertino/handbooks`) and `handbook.skip_verification` (default
`false`).

Resolve `domain` per `${CLAUDE_PLUGIN_ROOT}/references/handbook.md`'s
domain-resolution table. If ambiguous, ask directly.

## Step 1 — Load and parse the handbook

Read `<output_dir>/<domain>-handbook.md`. **If it doesn't exist, stop
here** and say plainly: "No `<domain>` handbook found at `<output_dir>` —
run `cupertino-handbook-draft` for this domain first." Parse each `##
Dimensions` → `### Dimension: <id> — <title>` block into
`{id, rule: <Rule text>, dimension: <title>, enforcement: <Enforcement
value>, detectionSignal: <Detection signal text>}` — the workflow script
cannot read this file itself (Workflow scripts have no filesystem access),
so this extraction happens here, in the skill.

## Step 2 — Determine target files

If the user's request names specific files/directories, use those as
`targetFiles`. Otherwise default to changed files: run `git status
--porcelain` and `git diff --name-only HEAD` to build the set of
staged/unstaged/untracked files, then filter to the domain's relevant file
types (CSS/component/markup files for `design`; source files for `code`;
test files for `testing`; markdown/doc files for `documentation`). **If
nothing has changed**, ask whether to run a full-project scan for this
domain instead of silently reporting no findings — a "nothing changed"
result and a "nothing to check" result are different things, and only the
user knows which was intended.

## Step 3 — Run the scan

**Preferred — Workflow orchestration.** If the **Workflow tool** is
available in this session (this skill invocation is your authorization):

```
Workflow({
  scriptPath: "${CLAUDE_PLUGIN_ROOT}/workflows/handbook-drift-scan.js",
  args: { repoPath: "<repo root, usually '.'>", domain: "<design|code|testing|documentation>", handbookRules: [{id, rule, dimension, enforcement, detectionSignal}, ...], targetFiles: [...], skipVerification: <from settings, default false> }
})
```

It dispatches one `handbook-drift-auditor` finder per rule, then — unless
`skip_verification` is set — an independent referee per candidate finding
plus a second-tier re-confirm for High-severity survivors. The finders/
referees are read-only by design; **you** write the report below from the
structured result.

**Fallback** (no Workflow tool) — for each rule, dispatch a
`handbook-drift-auditor` subagent with that rule's text, enforcement, and
detection signal against `targetFiles`. Then, unless `skip_verification`
is set, verify each candidate finding yourself by opening its cited
`evidence` and confirming the divergence is real.

## Step 4 — Write the report

Create `<output_dir>/HANDBOOK_CHECK-<domain>.md`:
- **Summary** — domain, files checked, findings by severity, findings by
  category (`violation`/`missing`), mechanical count, refuted count.
- **Findings table**, sorted by severity: rule id, category, evidence,
  title, suggested fix, mechanical (yes/no).
- **Refuted candidates** — brief list.
- If `injectionFlags` is non-empty, a prominent "⚠ Instruction-shaped
  content found" section.

Also write `<output_dir>/handbook_check_<domain>_summary.json` — the
workflow's own `findings` array, unmodified (`cupertino-handbook-fix`
filters on its exact shape: `{severity, title, evidence, category, ruleId,
suggestedFix, mechanical}`), alongside `{domain, checkedAt,
findingsBySeverity, byCategory, mechanicalCount}`.

## Present

Report: domain, files checked, findings by severity/category, mechanical
count (what `cupertino-handbook-fix` could act on if the user explicitly
authorizes it), refuted count. If a skill matching `self-assess-*` or
`andon-*` is present in this session's Skill list, name it as
complementary per `references/handbook.md`'s soft-detection protocol. If
`handbook.fix.mode` is `propose` (the default), note that applying any
mechanical finding requires setting it to `fix` first — do not offer to
apply anything from this skill itself, that's `cupertino-handbook-fix`'s
job.
