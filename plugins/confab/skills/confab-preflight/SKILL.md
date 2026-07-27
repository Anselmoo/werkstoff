---
name: confab-preflight
description: "Use when the user asks whether this repository is ready for confab audits to run successfully, wants a pre-flight/readiness check before running confab-dependency-audit, confab-assertion-audit, confab-contract-drift, or confab-agentic-reliability, or asks 'is confab set up correctly here'. Runs five independent checks and reports one readiness verdict per domain skill."
---

Run confab's readiness check for this repository. All five checks run
unconditionally — the underlying script wraps each one in its own
try/except so a crash in one check can never suppress the other four,
which is exactly the guarantee this skill promises (preflight-all-checks-run).

## Steps

1. Determine `repo_root` (default: current working directory, or the path
   the user named).
2. Run:
   ```
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/preflight.py" <repo_root> [--timeout-seconds N]
   ```
   Pass `--timeout-seconds` only if the user (or a `dependency_audit.timeout_seconds`
   setting you already know about) specifies a value other than the
   10-second default.
3. The script writes `analysis/confab/reports/PREFLIGHT.md` and
   `analysis/confab/preflight_summary.json` and prints a JSON summary of the four
   readiness verdicts (`dependency-audit`, `assertion-audit`,
   `contract-drift`, `agentic-reliability`) to stdout. Read that JSON.
4. Report to the user: the five check statuses and the four verdicts, in
   a short table. If any verdict is `not_ready` or `degraded`, name the
   specific check that caused it and what would need to change (e.g. "no
   manifest files found — dependency-audit has nothing to check yet").
5. Never describe a `degraded` registry-reachability result as "the
   registry is down" — the check only establishes whether OUR read-only
   lookup succeeded within the timeout, not the registry's actual global
   status. Report it as "could not confirm reachability," matching the
   rule that a registry timeout is never an affirmative verdict in either
   direction.

## What NOT to do

Do not hand-roll your own checks in place of the script — the "all five
checks always run" guarantee lives in `scripts/preflight.py`'s per-check
try/except structure, not in this file's instructions. If you think a
sixth check would be useful, mention it to the user as a suggestion; do
not add it ad hoc to this run's output.
