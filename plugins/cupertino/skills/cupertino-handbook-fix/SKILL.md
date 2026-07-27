---
name: cupertino-handbook-fix
description: "Use only when the user has explicitly enabled fix mode for a domain, to apply the mechanical findings from a prior cupertino-handbook-check pass. Trigger only on explicit requests like 'fix the mechanical handbook findings' AFTER the user has turned on fix mode — never infer consent from a check report alone. Never touches mechanical:false findings, never commits or pushes."
---

Apply only the mechanical findings from an existing `cupertino-handbook-check` report — nothing that needs design judgment, and nothing beyond what was already found and verified.

## Mode gate — checked before anything else

This skill's dispatch is itself gated by a PreToolUse hook: it reads `.claude/cupertino.local.md` for a `fix:` block containing `mode: fix`, and denies the dispatch outright if that setting isn't present. If you're executing this skill body, that gate already passed for this invocation — but if the user asks you to "just fix it" without having set this, **stop and report plainly** that `handbook.fix.mode` is not `fix`, and tell them what to add to `.claude/cupertino.local.md`:
```markdown
---
fix:
  mode: fix
---
```
Do not attempt any workaround.

## Steps

1. **Parse the domain**, locate `.cupertino/handbook_check_<domain>_summary.json` from the most recent `cupertino-handbook-check` run. If it doesn't exist, tell the user to run that check first.
2. **Validate the summary on read, not just on trust** — a stale or hand-edited findings file could be missing the fields this whole process gates on:
   ```bash
   cat ".cupertino/handbook_check_${domain}_summary.json" | python3 "${CLAUDE_PLUGIN_ROOT}/scripts/validators.py" handbook-check-summary
   ```
   If this exits non-zero, stop — do not attempt to guess or repair the missing fields yourself. Report the validator's errors and ask the user to re-run `cupertino-handbook-check`.
3. **Filter to `mechanical: true` findings only.** Everything else is explicitly out of scope for this skill — it requires design judgment `handbook-remediator` is built to refuse.
4. **Mark the fix pass active**, which the PreToolUse hook uses to block any `git commit`/`git push`/destructive command for the duration:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/state.py" set handbook-fix-active
   ```
5. **Run the fix pipeline** via the Workflow tool:
   ```
   Workflow({ scriptPath: "${CLAUDE_PLUGIN_ROOT}/workflows/handbook-fix.js", args: { findings: [...] } })
   ```
   This clusters findings by `(file, rule)`, dispatches `handbook-remediator` once per cluster (never touching anything outside the cited file:line, never verifying its own work), and immediately dispatches a **fresh, independent** `handbook-verifier` per finding — one that is never shown the remediator's own description, rationale, or confidence, only the original pre-fix evidence and the rule text. Both constraints are backstopped by the PreToolUse hook regardless of what the workflow script does.
6. **Clear the flag**:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/state.py" clear handbook-fix-active
   ```
7. **Report one accept/fail line per finding fixed** — the remediation outcome and the independent verifier's verdict, side by side, so a "fixed" claim that the verifier actually rejected is visible, not hidden.
8. **Never commit or push**, and never touch test files or CI configuration — this skill's job ends at the working tree.

## Output format

Mode-gate confirmation → validated findings count (mechanical vs. skipped) → per-finding accept/fail table (remediation status + verifier verdict) → explicit statement that nothing was committed or pushed.
