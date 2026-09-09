---
name: nacharbeit-status
description: "Use to report what nacharbeit has already run in this repository — the last lint, the last calibrated review with its sealed recall per family and blind spots, the backlog by tier with every opus- and human-tier entry named, the last fix pass and its post-check result, and an open fix lock with its age. Trigger on 'nacharbeit status', 'what did the plugin review find', 'is a fix pass still open', 'which findings need a human'. Read-only; reports on nacharbeit's own state only and has nothing to say about a repository nacharbeit has not run in."
---

Report the state on disk, and only that. The held-for-a-person list is the reason this
skill exists: opus- and human-tier findings are never auto-applied, so the only way
they get resolved is a person reading them here.

## Steps

1. **Read the state directory** (default `analysis/nacharbeit/`; `--state-dir` otherwise):

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/status.py"
   ```

2. **Lead with what blocks.** A `FAILED-*` marker newer than `run.json` means the JSON
   on disk is older than the run somebody watched fail. An open lock older than six
   hours is stale: every edit in the repository is being denied, and the release command
   is the first line of the answer.

3. **Then the held entries**, verbatim, one per line with plugin, file, tier and action.
   These are decisions, not tasks; do not offer to apply them.

4. **Then the numbers**, briefly: lint findings by rule, verified count, sealed recall per
   family and the blind spots it implies, fix tally.

## Output format

```
nacharbeit status — state analysis/nacharbeit
  lint: 41 finding(s); H-TIMEOUT=3, M-DUP-CONTENT=1, P-MARKETPLACE-MEMBER=7, S-DOCSTRING-USAGE=12 …
  review 2026-09-09T06:12:04Z rubric 3f9c1a2b7d0e: 2 calibration round(s), sealed recall 0.79 (Q 0.81, HQ 0.75, SQ 0.67, AQ 0.75, PQ 0.80, DQ 1.00); verified 164 + lint 41, judged collisions 24
        blind spots (sealed defects missed): 3 — test/plugins/fixtures/nacharbeit/sealed-2/skills/quill-lint/SKILL.md Q-OTHER-RIGIDITY; …
  backlog by tier: haiku 31, sonnet 96, opus 2, human 4
  held for a person (6; never auto-applied):
    [opus ] compass: plugins/compass/workflows/solve.js — design a real gate for each stage's declared output_contract …
    [human] andon: plugins/andon/skills/andon-loop/SKILL.md — decide whether andon-loop supports scoped/filtered runs …
  fix pass 2026-09-09T07:02:11Z (review 2026-09-09T06:12:04Z): 41 file(s), 9 excluded
  post-fix check 2026-09-09T07:41:50Z: 1 failed post-check(s) or a moved contract; lock released: False
  fix lock OPEN (50 files, age 9.3 h, STALE) — every edit outside it is denied; release with: python3 plugins/nacharbeit/scripts/post_fix_check.py --release-lock
```

## Rules

- **Never edit state** to make the status cleaner, and never delete a lock from here.
- **Never re-run a review or a fix** from this skill; it reports.
- **An empty state directory is a valid status**: "nacharbeit has not run here".

## Resources

- `scripts/status.py` — run; the report above is its output.
- `references/fix-scope-schema.md` — read to explain a stale lock.
