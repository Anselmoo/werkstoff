---
name: cupertino-handbook-draft
description: "Use when the user wants to create and persist a durable handbook for one domain — design, code, testing, or documentation — capturing the project's actual conventions (or honest scaffolded defaults where none exist) as a checkable rule per dimension. Trigger on 'write a code handbook', 'draft our design standards', 'create a testing handbook', or similar requests naming a domain and asking for a persisted, checkable artifact rather than a one-off answer."
---

Draft `.cupertino/<domain>-handbook.md` by analyzing this project one dimension at a time, never inventing evidence, and marking honestly what's scaffolded versus observed.

## Steps

1. **Parse the domain** from the first argument — must be exactly one of `code`, `design`, `testing`, `documentation`. If it's anything else, say so and stop; don't guess a mapping.
2. **Check for an existing handbook** at `.cupertino/<domain>-handbook.md`. If it exists, **ask the user explicitly** whether to overwrite before doing anything else — do not proceed silently. (A PreToolUse hook also enforces this: it refuses to overwrite an existing handbook file unless its first line is the literal marker `<!-- cupertino-overwrite-confirmed -->`. Only include that marker after the user has actually said yes.)
3. **Run the dimension fan-out** via the Workflow tool. First resolve or build the shared symbol-index snapshot: read `analysis/cupertino/current.json`; if missing or its `source_fingerprint` no longer matches, run
   ```
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/build_symbol_index.py" --repo-path . --plugin-name cupertino
   ```
   (single-flight lock makes concurrent callers safe -- see `references/parallel-safe-research-protocol.md`). For a repo well under ~50 tracked files the build overhead may not be worth it -- skip this and pass `symbolIndexPath: null`.
   ```
   Workflow({ scriptPath: "${CLAUDE_PLUGIN_ROOT}/workflows/handbook-draft.js", args: { domain: "<domain>", symbolIndexPath: "<resolved snapshot dir, or null>" } })
   ```
   This dispatches `handbook-dimension-analyst` once per dimension in the domain's fixed catalog (6 dimensions), each with exactly one dimension named — enforced structurally by the workflow's loop and backstopped by the PreToolUse hook, which denies any dispatch of that agent whose prompt doesn't contain exactly one `DIMENSION:` marker. Each candidate rule is then independently re-verified by a second, blind dispatch of the same agent type before you use it.
4. **Write the handbook** at `.cupertino/<domain>-handbook.md` with sections:
   - `## Dimensions` — one entry per dimension: the rule, its source (`analyzed` with the file:line evidence, or `scaffolded` with the note explaining no convention exists), and the verification verdict.
   - `## Exceptions & waivers` — empty to start; this is where future waivers get recorded.
   - `## Change log` — one entry noting this handbook was drafted, and when.
5. **Write the sidecar** at `.cupertino/<domain>-handbook_summary.json` with `{domain, generatedAt, dimensions: [...]}`, matching the schema a PreToolUse hook validates on write (each dimension needs `dimension`, `rule`, `sourceMode`, and either `evidence` (if analyzed) or `note` (if scaffolded) — a missing gating field is rejected, not defaulted).
6. **Never invent evidence.** If a dimension analyst reports `scaffolded` because the project genuinely has no visible convention, write it that way plainly — do not upgrade it to `analyzed` to make the handbook look more grounded than it is.

## Output format

Domain confirmation → overwrite check result → the six dimensions with source/evidence/verdict → confirmation that both files were written.
