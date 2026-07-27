---
name: confab-dependency-audit
description: "Use when the user asks to audit declared dependencies for hallucinated, nonexistent, or typosquat-adjacent packages, wants confab's dependency audit run, or asks whether package.json/requirements.txt/pyproject.toml/Cargo.toml/go.mod/Gemfile entries actually exist. Performs bounded, read-only registry lookups with a mandatory-unless-flagged independent verification pass."
---

Audit this repository's declared dependencies for hallucination and
typosquat-adjacent naming. The registry lookups themselves — and their
timeout bound, and the rule that an unreachable registry is reported as
`skipped` rather than any kind of verdict — are enforced by
`scripts/dependency_audit.py` and `scripts/lib/registry.py`, not by these
instructions. Your job is to orchestrate the agent judgment layer around
that deterministic core and present the result.

## Steps

1. Determine `repo_root`, and `timeout_seconds` (default 10; only override
   if the user or a `dependency_audit.timeout_seconds` setting says
   otherwise — never silently raise it past 60).
2. Determine whether the user explicitly asked to skip verification
   (`skip_verification: true`). If they did not say so explicitly, treat
   it as `false` — verification runs by default.
3. Optionally, for judgment calls the deterministic parser can't make on
   its own (ambiguous or scoped/private-looking package names, names that
   look engineered rather than organically typo'd), dispatch the
   `dependency-auditor` agent in Find mode over the repo's manifest files.
   Ask it to return `{"findings": [...]}` in the shared finding schema.
   Write its output to a scratch file, e.g.
   `${CLAUDE_PLUGIN_ROOT}/../analysis/confab/tmp/agent_findings.json` (or any
   scratch path — it is only ever read once, by the next step).
4. Run:
   ```
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/dependency_audit.py" <repo_root> \
       --timeout-seconds <N> \
       [--skip-verification] \
       [--agent-findings <path-from-step-3>]
   ```
   This single invocation performs the manifest parse, the bounded
   registry lookups, the typosquat heuristic, the mandatory-unless-flagged
   independent re-check of every finding (including any you supplied via
   `--agent-findings` — they get the same re-check, never taken on
   faith), and writes `analysis/confab/reports/DEPENDENCY_AUDIT.md` and
   `analysis/confab/dependency_audit_summary.json` in the shared finding schema.
5. Report the finding count and the top few findings to the user, and
   point them at the report path. If any findings have
   `category: "registry-unreachable"`, say so explicitly and note they
   are not evidence of anything — just an unconfirmed lookup — never
   phrase them as "these might be hallucinated."

## What NOT to do

- Do not call a registry yourself with `curl`/`pip index`/`npm view` —
  always go through the script, which is the only place the timeout bound
  and the skip-vs-verdict classification are enforced.
- Do not skip step 4's verification behavior by omitting the script's own
  re-check — there is no flag for that; `--skip-verification` on this
  script controls the SAME verification the rule requires, and omitting
  the flag (the default) is what keeps it mandatory.
- Do not report a `not_found` lookup outcome as "hallucinated" without
  noting it survived independent re-verification — that's what makes it
  a confirmed finding rather than a first-pass guess.
