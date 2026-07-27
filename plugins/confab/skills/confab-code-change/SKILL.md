---
name: confab-code-change
description: "Use when the user asks for a pre-commit quality check on staged or uncommitted changes, wants a quick confab pass over 'what I just changed' before committing, or asks 'is this diff okay to commit'. Only runs the domains whose file patterns match the changed files, and always produces an advisory verdict that never blocks the commit."
---

Run a fast, changed-files-scoped confab pass across whichever domains are
actually relevant to what changed. This is a lighter-weight sibling of the
four full domain-audit skills — each Find-phase pass here is a single,
un-verified check (the code-change verdict is advisory by construction,
so it does not carry the same mandatory-verification guarantees the full
audits do). If the user wants a fully verified audit, tell them to run
the specific `confab-*-audit` skill instead.

## Steps

1. Determine `repo_root`. Get the changed-file list:
   ```
   git -C <repo_root> diff --staged --name-only
   ```
   (or `git diff HEAD --name-only` if the user means uncommitted rather
   than staged changes — ask if ambiguous). Write the list to a scratch
   JSON file as a plain array of repo-relative paths.
2. Run:
   ```
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/code_change_review.py" <repo_root> \
       --changed-files-json <path-from-step-1>
   ```
   with NO `--domain-findings` yet, just to see which domains matched. If
   it exits 1, it printed "zero domains matched" to stderr — relay that
   to the user verbatim and stop; there is nothing to review.
3. For each matched domain printed in step 2's `matchedDomains`, produce a
   lightweight findings JSON scoped to only the matched files:
   - `dependency_audit`: only if a manifest file changed. Dispatch the
     `dependency-auditor` agent (or, more simply, run
     `scripts/dependency_audit.py <repo_root>` — it's fast enough for a
     pre-commit check and already does the full bounded-timeout lookup).
   - `assertion_audit`: dispatch `assertion-auditor` in Find mode only,
     scoped to the changed source/test files.
   - `contract_drift`: dispatch `contract-auditor` in Find mode only,
     scoped to the changed files.
   - `agentic_reliability`: dispatch `agentic-reliability-auditor` in Find
     mode only, scoped to the changed skill/agent/workflow files.
   Write each domain's findings to its own scratch JSON file.
4. Re-run the script, now passing every matched domain's findings:
   ```
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/code_change_review.py" <repo_root> \
       --changed-files-json <path-from-step-1> \
       --domain-findings dependency_audit=<path> \
       --domain-findings assertion_audit=<path> \
       ...
   ```
   (only pass `--domain-findings` for domains that actually matched).
   This writes `analysis/confab/reports/CODE_CHANGE_REVIEW.md` with one section
   per matched domain (unmatched domains are omitted entirely — never
   zero-filled) and a verdict line that always reads `ADVISORY: ...` and
   never suggests blocking anything.
5. Report the verdict line and per-domain finding counts to the user.
   Always phrase the summary as advisory — e.g. "N findings worth a look
   before you commit, but nothing here blocks you."

## What NOT to do

- Do not tell the user their commit is "blocked" or "failing" — this
  skill has no gate, only advice. If the user wants a hard gate, that's a
  git hook they'd configure themselves, not something this skill does.
- Do not run a domain that didn't match — e.g. don't dispatch
  `assertion-auditor` if no source or test file changed.
- Do not invent a zero-finding section for a domain that didn't match,
  either in the report or in your summary to the user.
