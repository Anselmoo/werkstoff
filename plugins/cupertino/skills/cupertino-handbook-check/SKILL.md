---
name: cupertino-handbook-check
description: "Use when the user wants to compare new or changed work against an existing domain handbook to find divergence. Trigger on 'does this comply with our handbook', 'check this against our standards', 'audit these files against the code handbook'. Read-only — never modifies target files. Zero findings is a valid, expected outcome, not something to work around."
---

Check files against an existing handbook, one rule at a time, verifying every finding independently. Never touch the target files.

## Steps

1. **Parse the domain**, confirm `.cupertino/<domain>-handbook.md` exists (if not, point the user to `cupertino-handbook-draft`).
2. **Determine target files**: use the files the user named, or if they asked for a check but didn't say what changed, **ask whether to run a full-project scan** rather than silently picking a scope for them.
3. **Mark the check as active** so the write/no-mutation guarantees below are enforced at the tool-call layer, not just by convention:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/state.py" set handbook-check-active
   ```
4. **Read the handbook** and extract its rule list (one `{dimension, rule}` per handbook entry).
5. **Run the check** via the Workflow tool:
   ```
   Workflow({ scriptPath: "${CLAUDE_PLUGIN_ROOT}/workflows/handbook-check.js", args: { rules: [...], targetFiles: [...] } })
   ```
   This dispatches `handbook-drift-auditor` once per rule (never bundling rules), then independently re-verifies every individual finding at its exact `file:line` before it counts — a PreToolUse hook backstops both the one-rule-per-dispatch and one-location-per-verify constraints regardless of what the workflow script does. Findings that don't survive re-verification are dropped, not reported.
6. **Clear the active flag** when done:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/state.py" clear handbook-check-active
   ```
7. **Write the report** at `.cupertino/HANDBOOK_CHECK-<domain>.md` — a findings table with severity (High/Medium/Low), evidence (`file:line`), and whether each finding is mechanical (fixable without design judgment) or not — plus the sidecar `.cupertino/handbook_check_<domain>_summary.json`, whose schema is validated on write by the same PreToolUse hook (a finding missing `severity`, `mechanical`, or `line` is rejected outright, never defaulted). Both files live under `.cupertino/`, the plugin's one declared output directory — a PreToolUse hook denies either write if it targets anywhere else.
8. **If there are zero findings, say so plainly and stop there.** That is a valid, expected outcome. Never lower the severity bar or manufacture a marginal finding just to avoid reporting an empty result — an honest "no divergence found" is the correct output, not a failure to explain away.

## Output format

Domain/handbook confirmation → target file scope (and how it was determined) → the findings table (or the explicit zero-findings statement) → confirmation both artifacts were written.
