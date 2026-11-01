---
name: cupertino-handbook-check
description: "Use when the user wants to compare new or changed work against an existing domain handbook at .cupertino/DOMAIN-handbook.md (one file per domain) to find divergence. Trigger on 'does this comply with our handbook', 'audit these files against the code handbook', 'check this against the code handbook'. Requires a handbook previously produced by cupertino-handbook-draft. Not for repo-wide conventions written in CLAUDE.md or .claude/house-rules.md — use befund:befund-lint-audit for those. Read-only — never modifies target files. Zero findings is a valid, expected outcome, not something to work around."
---

Check files against an existing handbook, one rule at a time, verifying every finding independently. Never touch the target files.

## Steps

1. **Parse the domain**, confirm `.cupertino/<domain>-handbook.md` exists (if not, point the user to `cupertino-handbook-draft`).
2. **Determine target files**: use the files the user named, or if they asked for a check but didn't say what changed, **ask whether to run a full-project scan** rather than silently picking a scope for them.
3. **Mark the check as active** so the write/no-mutation guarantees below are enforced at the tool-call layer, not just by convention:
   ```bash
   python3 -B "${CLAUDE_PLUGIN_ROOT}/scripts/state.py" set handbook-check-active
   ```
4. **Read the handbook** and extract its rule list (one `{dimension, rule, sourceMode}` per handbook entry; `sourceMode` is `analyzed` for a convention the repo actually shows, `scaffolded` for an invented default). Also read `.claude/cupertino.local.md` if it exists: `enforceScaffolded` is `true` only when its frontmatter has `handbook:` with `enforceScaffolded: true`; otherwise `false`. Never infer it.
5. **Run the check** via the Workflow tool:
   ```
   Workflow({ scriptPath: "${CLAUDE_PLUGIN_ROOT}/workflows/handbook-check.js", args: { rules: [...], targetFiles: [...], enforceScaffolded: false } })
   ```
   Only observed rules are enforced. Scaffolded rules are defaults nobody observed, so checking working code against them flags code that is fine; unless `enforceScaffolded` is `true` the workflow skips them and returns how many as `skippedScaffolded` (a count, never findings). This dispatches `handbook-drift-auditor` once per rule (never bundling rules), then independently re-verifies every individual finding at its exact `file:line` before it counts — a PreToolUse hook backstops both the one-rule-per-dispatch and one-location-per-verify constraints regardless of what the workflow script does. Findings that don't survive re-verification are dropped, not reported.
6. **Clear the active flag** when done — and immediately, before stopping, if step 4 or step 5 fails or is interrupted, rather than leaving it set:
   ```bash
   python3 -B "${CLAUDE_PLUGIN_ROOT}/scripts/state.py" clear handbook-check-active
   ```
7. **Write the report** at `.cupertino/HANDBOOK_CHECK-<domain>.md` — a findings table with severity (High/Medium/Low), evidence (`file:line`), and whether each finding is mechanical (fixable without design judgment) or not, plus one line stating how many scaffolded rules were skipped — and the sidecar `.cupertino/handbook_check_<domain>_summary.json`, whose schema is validated on write by the same PreToolUse hook (a finding missing any field below is rejected outright, never defaulted). Both files live under `.cupertino/`, the plugin's one declared output directory — a PreToolUse hook denies either write if it targets anywhere else.

   The sidecar has one shape. `generatedAt` is an ISO-8601 UTC timestamp, `quotedLine` is the offending line verbatim (the fix pass finds its target by that text, not by `line`), `endLine` is optional and only for a finding that spans lines, and `skippedScaffolded` is the count the workflow returned. Validate it before writing: `echo '<json>' | python3 -B "${CLAUDE_PLUGIN_ROOT}/scripts/validators.py" handbook-check-summary`.

   Sidecar shape, populated:
   ```json
   {"domain": "design", "generatedAt": "2026-10-20T12:00:00Z", "skippedScaffolded": 2, "findings": [{"rule": "no-inline-styles", "file": "src/Card.tsx", "line": 42, "severity": "Medium", "title": "Inline style on card container", "evidence": "src/Card.tsx:42", "quotedLine": "<div style={{ padding: 8 }}>", "mechanical": true, "suggestedFix": "Replace the inline style with the .card-padding class", "verification": {"verdict": "confirmed"}}]}
   ```
   Sidecar shape, zero findings:
   ```json
   {"domain": "design", "generatedAt": "2026-10-20T12:00:00Z", "skippedScaffolded": 0, "findings": []}
   ```
8. **If there are zero findings, say so plainly and stop there.** That is a valid, expected outcome. Never lower the severity bar or manufacture a marginal finding just to avoid reporting an empty result — an honest "no divergence found" is the correct output, not a failure to explain away.

## Output format

Domain/handbook confirmation → target file scope (and how it was determined) → the findings table (or the explicit zero-findings statement) → confirmation both artifacts were written.
