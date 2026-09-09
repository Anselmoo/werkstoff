---
name: self-assess-lint-audit
description: Extracts discrete, checkable rules from .claude/house-rules.md (or CLAUDE.md as a best-effort fallback) and dispatches finders to verify violations against the actual code, capping dispatch at lint_max_rules. Reports violations only -- for mechanical fixes see self-assess-idiom-fix. Use when the user asks to "check our conventions", "check this code against our standards", "does the code follow the conventions we wrote down", "audit against house rules", "verify code follows CLAUDE.md", or as part of self-assess-autopilot's CHECK phase. Not for auditing work against a cupertino domain handbook under .cupertino/ -- use cupertino:cupertino-handbook-check for that.
---

# self-assess-lint-audit

Verify the codebase actually follows its own documented conventions.

## Step 0: Settings gate

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/self_assess_cli.py check-enabled --repo <repo_root> --skill self-assess-lint-audit
```

A non-zero exit means the skill is disabled -- stop and tell the user plainly, quoting the
stderr message. On success, the JSON on stdout carries the resolved settings, including
`lint_max_rules` (used in Step 2's cap) and `skip_verification` (used in Step 3).

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
silently dropped. For example:

```markdown
### Rules not checked this run

- **No bare `except:` clauses** (source: house-rules.md) -- skipped: over lint_max_rules cap (12)
```

## Step 3: Verify violations

Before dispatching, resolve the shared symbol-index snapshot. Read
`analysis/self-assess/current.json`; if missing or its `source_fingerprint`
no longer matches the repository, run

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/build_symbol_index.py --repo-path . --plugin-name self-assess
```

(single-flight lock makes concurrent callers safe -- see
`references/parallel-safe-research-protocol.md`). For a repo well under
~50 tracked files the build overhead may not be worth it (see
`references/parallel-safe-research-protocol.md`'s Scale guidance) -- skip this and
dispatch without it.

Unless `skip_verification` is set, dispatch `convention-auditor` once per dispatched rule (or
batched, at the agent's discretion) to find and confirm violations by reading the actual code
-- never invent a convention not documented in the source file. When the snapshot is available,
hand it to `convention-auditor` as additional evidence for locating symbol definitions and call
sites relevant to each rule.

## Step 4: Validate and write

Build `lint_audit_summary.json` with the dispatched rules, their verdicts, and the
`rules_skipped` list, then validate it before writing:

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/self_assess_cli.py validate-artifact --kind lint_audit_summary --file <path-or-inline-json>
```

The validator rejects the artifact if rules were extracted beyond the cap but `rules_skipped`
is empty -- that combination means rules were dropped silently, which is not permitted. If
validate-artifact rejects for this reason, populate `rules_skipped` from the capped list (the
`skipped` output of Step 2's `cap-lint-rules` call) and re-run validate-artifact before writing.

Resolve both output paths:

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/self_assess_cli.py resolve-output-path --repo <repo_root> --filename LINT_AUDIT.md
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/self_assess_cli.py resolve-output-path --repo <repo_root> --filename lint_audit_summary.json
```

A non-zero exit here means the configured `output_dir` or filename escapes the plugin's write
scope -- stop, do not write anywhere else instead. On success, write `LINT_AUDIT.md` (a
human-readable report listing each dispatched rule's verdict and any violations found, plus the
"Rules not checked this run" section from Step 2 for anything in `rules_skipped`) and
`lint_audit_summary.json` to the resolved paths using the Write tool.

## Read-only constraint

Never use Write/Edit outside the resolved output paths, and never auto-fix a violation found
here -- that is `self-assess-idiom-fix`'s scope for idiom findings, not this skill's.
