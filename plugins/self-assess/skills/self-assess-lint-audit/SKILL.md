---
name: self-assess-lint-audit
description: This skill should be used when the user asks to "check our conventions", "audit against house rules", "verify code follows CLAUDE.md", or as part of self-assess-autopilot's CHECK phase. Extracts discrete rules from .claude/house-rules.md (or CLAUDE.md as a best-effort fallback) and verifies violations, capping finder dispatch at lint_max_rules.
version: 0.1.0
---

# self-assess-lint-audit

Verify the codebase actually follows its own documented conventions.

## Step 0: Settings gate

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/self_assess_cli.py check-enabled --repo <repo_root> --skill self-assess-lint-audit
```

## Step 1: Load conventions, with graceful degradation

Read `.claude/house-rules.md`. If absent, fall back to `CLAUDE.md` and label every rule
extracted from it `source: "CLAUDE.md (best-effort)"` in the output -- never claim
`house-rules.md` was the source when it was not present.

## Step 2: Parse into discrete rules, then cap dispatch

Extract every discrete, checkable rule from the source doc. Rule `lint-max-rules-cap` requires
capping finder dispatch at `lint_max_rules` (default 12) even though extraction itself is
unbounded:

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/self_assess_cli.py cap-lint-rules --rules <json list of extracted rules> --max-rules <settings.lint_max_rules>
```

The `dispatched` list is what `convention-auditor` actually checks; the `skipped` list MUST be
logged in `LINT_AUDIT.md` under an explicit "Rules not checked this run" section -- never
silently dropped.

## Step 3: Verify violations

Unless `skip_verification` is set, dispatch `convention-auditor` once per dispatched rule (or
batched, at the agent's discretion) to find and confirm violations by reading the actual code
-- never invent a convention not documented in the source file.

## Step 4: Validate and write

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/self_assess_cli.py validate-artifact --kind lint_audit_summary --file <path-or-inline-json>
```

The validator rejects the artifact if rules were extracted beyond the cap but `rules_skipped`
is empty -- that combination means rules were dropped silently, which is not permitted.

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/self_assess_cli.py resolve-output-path --repo <repo_root> --filename LINT_AUDIT.md
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/self_assess_cli.py resolve-output-path --repo <repo_root> --filename lint_audit_summary.json
```

## Read-only constraint

Never use Write/Edit outside the resolved output paths, and never auto-fix a violation found
here -- that is `self-assess-idiom-fix`'s scope for idiom findings, not this skill's.
