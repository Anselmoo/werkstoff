---
name: cupertino-handbook-draft
description: Analyzes a target project (or scaffolds sensible defaults for an empty/near-empty one) for one of four domains -- design, code, testing, documentation -- and writes a persisted, project-specific handbook artifact of that domain's actual conventions plus a machine-readable summary sidecar. Use when the user asks to draft/create/generate a design handbook, code style handbook, testing conventions handbook, or documentation handbook, or wants a durable "north star" of this project's conventions instead of a one-shot review. This is the first stage of cupertino's handbook lifecycle (draft -> apply -> check -> fix); the artifact it writes is what cupertino-handbook-apply, cupertino-handbook-check, and cupertino-handbook-fix all read. Not for a one-shot design/code review with no persisted artifact -- use cupertino-review or the relevant single-technique cupertino-* skill for that.
---

Analyze a target project for one domain — `design`, `code`, `testing`, or
`documentation` — and write a persisted handbook artifact recording that
domain's actual conventions, each rule concrete enough to be checked
against later. This is the entry point to `cupertino`'s handbook lifecycle
(`draft` → `apply` → `check` → `fix`); see `${CLAUDE_PLUGIN_ROOT}/references/handbook.md`
for the shared vocabulary and domain-resolution rule every one of the 4
lifecycle skills uses.

Fully self-contained: this skill never invokes `self-assess` or `andon`
skills, agents, or workflows, even when they're installed alongside
`cupertino` — see `references/handbook.md`'s soft-detection protocol for
how it mentions them instead.

## Step 0 — Load settings and resolve domain

Read `.claude/cupertino.local.md` if it exists (see
`${CLAUDE_PLUGIN_ROOT}/references/handbook-settings.md`). If `enabled:
false`, stop and say so. Note `handbook.output_dir` (default
`docs/cupertino/handbooks`), `handbook.domains` (default `[]` = no
restriction), and `handbook.skip_verification` (default `false`).

Resolve `domain` per `${CLAUDE_PLUGIN_ROOT}/references/handbook.md`'s
domain-resolution table. If ambiguous, ask directly rather than guessing.
If `handbook.domains` is non-empty and doesn't include the resolved
domain, stop and say this project's settings restrict handbooks to the
listed domains. If the user's request names more than one domain, repeat
Steps 1-3 once per domain, sequentially, each producing its own separate
artifact — never merge domains into one file.

## Step 1 — Read the domain's dimension catalog

Read `${CLAUDE_PLUGIN_ROOT}/references/handbook-<domain>.md` for the
dimension table. Build the `dimensions` list to pass downstream: one entry
per row, `{id, title, rationale, detectionSignalHint}` — `rationale` and
`detectionSignalHint` come from that dimension's own subsection in the
catalog file (not just the table row, which is only a summary index).

## Step 2 — Run the scan

**Preferred — Workflow orchestration.** If the **Workflow tool** is
available in this session (this skill invocation is your authorization):

```
Workflow({
  scriptPath: "${CLAUDE_PLUGIN_ROOT}/workflows/handbook-draft-scan.js",
  args: { repoPath: "<repo root, usually '.'>", domain: "<design|code|testing|documentation>", dimensions: [{id, title, rationale, detectionSignalHint}, ...], skipVerification: <from settings, default false> }
})
```

It dispatches one `handbook-dimension-analyst` finder per dimension, then
— unless `skip_verification` is set — an independent referee per candidate
rule (demoting an invalid claim's `sourceMode` rather than dropping the
dimension). The finders/referees are read-only by design; **you** write
the artifact below from the structured result.

**Fallback** (no Workflow tool) — for each dimension, dispatch a
`handbook-dimension-analyst` subagent with that dimension's `rationale`
and `detectionSignalHint`, asking it to propose one candidate rule with
`sourceMode`. Then, unless `skip_verification` is set, verify each
candidate yourself by opening its cited `source` (if `analyzed`) and
confirming the rule is concrete enough to check later — demote to
`scaffolded` with a note if not.

## Step 3 — Write the artifact

Fill `${CLAUDE_PLUGIN_ROOT}/assets/handbook-template.md`'s shape with the
scan's `dimensions` result — one `## Dimensions` block per entry, in the
same order as the dimension catalog. Frontmatter: `domain`, `generated`
(today's date), `sourceMode` (the scan's `overallSourceMode`), `dimensions`
(the list of ids), `version: 1`. `## Exceptions & waivers` starts as an
empty table. `## Change log` gets one line: "Initial draft (`sourceMode:
<value>`)."

Write to `<output_dir>/<domain>-handbook.md`. **If a file already exists at
that path, do not silently overwrite it** — tell the user plainly and ask
whether to overwrite, or write to `<domain>-handbook.new.md` instead and
say so.

Also write `<output_dir>/<domain>-handbook_summary.json`:
`{"domain": "...", "generatedAt": "<ISO date>", "sourceMode": "...",
"ruleCount": N, "dimensions": [{"id": "...", "title": "...",
"enforcement": "..."}]}` — the sidecar `cupertino-handbook-apply` and
`cupertino-handbook-check` read instead of reparsing the markdown prose.

## Present

Report: domain, `sourceMode` breakdown (how many dimensions were analyzed
vs. scaffolded vs. demoted by the referee), rule count, and the artifact
path. If a skill matching `self-assess-*` or `andon-*` is present in this
session's Skill list, name it as complementary per
`references/handbook.md`'s soft-detection protocol (never invoke it).
Suggest running `cupertino-handbook-apply` before starting new work in this
domain, or `cupertino-handbook-check` once new work exists to compare
against this artifact.
