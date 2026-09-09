---
name: nacharbeit-lint
description: "Use to run the mechanical half of the nacharbeit rubric — 90 script-checkable rules over a plugin's skills, agents, commands, workflows, hooks, scripts, report viewers, manifest, README, CHANGELOG and docs wiring — with no model in the loop and no tokens spent. Trigger on 'lint this plugin', 'does this plugin meet the Anthropic standard mechanically', 'check the frontmatter and hooks.json', 'nacharbeit lint'. Reports findings by rule; never fixes anything (that is nacharbeit-fix) and never judges prose (that is nacharbeit-review)."
---

Everything a script can decide is decided here, so the model finders downstream never
have to. The linter asserts itself before it grades anything: a rule that cannot fail
is not a rule.

## Steps

1. **Prove the instrument first.** Run the calibration; it plants one defect per rule,
   checks a clean plugin stays silent, blanks each rule in turn to prove it load-bearing,
   and checks the rubric's tables and the linter's rule set agree:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/test_nacharbeit_lint.py"
   ```

   Only proceed on `GREEN`. A `RED` line names the rule that is broken; report it and stop
   — a linter whose calibration fails has no verdict to give.

2. **Lint the targets**, writing the JSON the review consumes:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/nacharbeit_lint.py" plugins/<name> [plugins/<other> ...] \
     --docs-root docs --out analysis/nacharbeit/lint.json
   ```

   Drop `--docs-root` when the repository has no docs site; the `D-*` rules then do not
   run. `--marketplace` defaults to `.claude-plugin/marketplace.json` when it exists.

3. **Read the `skipped` list before the findings.** A rule listed there (no `node`, no
   viewer checker) was not evaluated; silence on it is not a pass.

4. **Report by rule, then by file**, with the claim and the fix for each finding. Do not
   apply any fix, however mechanical: the fix pass runs under a lock and a blind
   verifier for a reason.

## Output format

```
321 files: skill=72, agent=41, command=9, reference=33, workflow=13, hooks=6, hookscript=7, script=92, viewer=8, manifest=10, readme=10, changelog=10, docs=10
     3  H-TIMEOUT
     1  M-DUP-CONTENT
     7  P-MARKETPLACE-MEMBER
- [minor] H-TIMEOUT  plugins/andon/hooks/hooks.json:9
    the PreToolUse command handler sets no integer `timeout`
- [major] P-MARKETPLACE-MEMBER  plugins/andon/.claude-plugin/plugin.json
    description differs from the marketplace copy (run `rrt fields`)
  SKIPPED S-JS-SYNTAX: node is not on PATH

Findings: 11 over 3 plugins (1 major, 8 minor, 2 nit); 1 rule skipped.
Every finding is haiku-tier except P-MARKETPLACE-MEMBER (human: the marketplace entry lives outside the plugin).
Next: nacharbeit-review for the judgement rules, or nacharbeit-fix to apply these under the lock.
```

## Rules

- **Calibration before verdict, every time.** Step 1 is not optional and not cached.
- **Findings are data, not failure.** The linter exits 0 on a completed scan; a non-zero
  exit means it could not scan, which is reported as such.
- **Never edit the file being graded**, and never edit the rubric to make a finding go
  away — the rubric hash rides in every run.

## Resources

- `scripts/test_nacharbeit_lint.py` — run first; the sabotage calibration.
- `scripts/nacharbeit_lint.py` — run; the linter. `--help` lists every flag.
- `scripts/check_viewer_conformance.py`, `scripts/verify_hooks_deny.py` — vendored
  checkers the `A-*` and hook post-checks delegate to; the linter imports the first.
- `references/rubric.md` — read to resolve any rule id in a finding.
