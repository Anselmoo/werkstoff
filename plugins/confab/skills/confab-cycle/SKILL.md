---
name: confab-cycle
description: "Use when the user asks for a bounded self-optimization loop that re-runs confab's audits until convergence or a pass cap, wants to 'run the confab cycle', 'keep fixing findings until done', or asks for propose-only vs fix-mode passes. Runs at most max_passes_per_invocation (default 5) passes, applies fixes only in fixable domains, and stops early on convergence — every bound is enforced by scripts/cycle_engine.py, not by this file's instructions."
---

Run confab's bounded self-optimization loop: repeatedly find the
"constraint" domain (the one with the most urgent open findings), audit
it, and — in fix mode — apply or draft fixes, until the loop converges or
hits its pass cap. The pass cap, the reopen thrash-guard, the fixable-
domain gating, and the convergence check are all enforced by
`scripts/cycle_engine.py` and `scripts/lib/ledger.py`; this file only
describes how to drive that engine. If your own count of passes ever
disagrees with what the engine reports, trust the engine — it is the
source of truth, not your running tally.

## Setup (once per invocation)

1. Determine `repo_root`, `mode` (`"fix"` or `"propose"` — default
   `"propose"` unless the user explicitly asked to apply fixes),
   `max_passes` (default 5, never pass a value above 20 to the engine —
   it will refuse), and `max_reopens` (default 3, never above 10).
2. Generate one `invocation_id` for this whole run (e.g.
   `python3 -c "import uuid; print(uuid.uuid4())"`) and reuse it for every
   symbol-index build this invocation needs — never build a fresh one per
   pass or per domain. This is what makes the symbol-index snapshot
   shared rather than rebuilt (rule: symbol-index-shared-per-invocation).
   Resolve it now:
   ```
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/symbol_index_cli.py" resolve <repo_root> --invocation-id <invocation_id>
   ```
   This is the "CLI wrapper the cycle skill points you at" that
   `confab-assertion-audit` and `confab-contract-drift`'s "Shared symbol
   index" sections already reference — tell those domain skills this same
   `invocation_id` when dispatching them so they hit the cache instead of
   rebuilding.

## Per-pass loop

Repeat the following until the engine tells you to stop:

3. Ask the engine what to do next:
   ```
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/cycle_engine.py" plan-next-pass <repo_root> \
       --max-passes <max_passes> --mode <mode>
   ```
   If this exits non-zero, the pass cap is already reached — stop the
   loop immediately and go to "Wrap up" below. Otherwise it prints
   `{"passNumber": N, "domain": "...", "mode": "..."}`.
4. Run that domain's audit skill's Find (and, per that domain's own
   rules, Verify) phase, scoped efficiently since you likely already have
   recent findings from a prior invocation — reuse `analysis/confab/<domain>_summary.json`
   if it's fresh, otherwise re-run the audit as that skill's own SKILL.md
   describes. Do not weaken that domain's own mandatory-verification rules
   just because you're inside a cycle pass — `assertion_audit` still runs
   its Verify phase unconditionally, `contract_drift` and
   `agentic_reliability` still run theirs unless explicitly skipped.
5. For each open finding in the constraint domain, decide its handling:
   - **mode is `"propose"`**: never apply anything. For a fixable finding
     (see below), still just describe the proposed fix in your report —
     do not dispatch `confab-remediator` at all in propose mode.
   - **mode is `"fix"` and the finding IS in confab's fixable set**
     (`dependency_audit` any category, `contract_drift` any category,
     `agentic_reliability` category `excessive-tool-grant` only — check
     with the same table `scripts/lib/constants.py FIXABLE_DOMAINS`
     encodes, don't just guess): open a remediation scope, dispatch the
     remediator, then close the scope:
     ```
     python3 "${CLAUDE_PLUGIN_ROOT}/scripts/remediation_scope_cli.py" open <repo_root> \
         --finding-id <id> --domain <domain> --category <category> \
         --target-file <repo-relative file>
     ```
     If this exits 3, the finding is NOT fixable — the script refused to
     even open a scope for it. Treat it as advisory and do not dispatch
     `confab-remediator`; this can happen even in fix mode if a finding's
     category was miscategorized upstream, and the script is the
     authority here, not your own read of the finding.
     If it exits 0, dispatch `confab-remediator` with exactly this one
     finding. A `PreToolUse` hook enforces that its one `Edit` call must
     target the locked file and that no second edit is possible in this
     scope — you do not need to police that yourself. After the
     remediator returns, run:
     ```
     python3 "${CLAUDE_PLUGIN_ROOT}/scripts/remediation_scope_cli.py" close <repo_root>
     ```
   - **the finding is in `assertion_audit`, or `agentic_reliability`
     outside `excessive-tool-grant`**: this is draft-only or advisory —
     never open a remediation scope for it, never dispatch
     `confab-remediator`. For `assertion_audit` specifically, you may ask
     the `assertion-auditor` agent to run in **Suggest mode** to draft a
     replacement assertion, but that draft is reported, never applied —
     no `Edit` call happens for it, ever.
6. Build this pass's outcome record and tell the engine:
   ```json
   {"passNumber": N, "domain": "...", "mode": "fix"|"propose",
    "outcomes": [{"findingId": "...", "category": "...", "evidence": "...",
                   "severity": "...", "outcome": "fixed"|"drafted"|"blocked"|"reopened",
                   "blockReason": "... (required when outcome is \"blocked\")"}]}
   ```
   Use `"fixed"` only for a finding `confab-remediator` returned
   `status: "applied"` for. Use `"blocked"` for one it returned
   `status: "blocked"` for, or one you determined is not fixable — and
   always copy its `reason` into `blockReason` here; the engine rejects
   (exit 2) any `"blocked"` outcome with an empty `blockReason` rather
   than accepting a blocked finding with no explanation on record. Use
   `"drafted"` for an assertion-audit Suggest-mode draft. Use
   `"reopened"` for a finding that was closed in a prior pass/invocation
   but is open again this pass. Write this to a scratch JSON file and run:
   ```
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/cycle_engine.py" record-pass-result <repo_root> \
       --pass-json <path> --max-reopens <max_reopens> --max-passes <max_passes>
   ```
   This is the ONLY place ledger state changes — do not hand-edit
   `analysis/confab/ledger.json` yourself. The script rejects (exit 2) any
   `"fixed"` outcome for a non-fixable domain/category or for a
   `"propose"`-mode pass; if you see that rejection, you made a mistake
   in step 5 — fix your outcome record, don't retry with a different
   claim to force it through.
   It prints `{"converged": bool, "shouldContinue": bool, ...}`. If
   `shouldContinue` is `false`, stop the loop — either the pass cap was
   reached or the pass converged (closed zero findings and produced zero
   fix/draft outcomes). Do not start another `plan-next-pass` call after
   `shouldContinue: false`.

## Wrap up

7. `analysis/confab/reports/CONFAB_CYCLE.md` already has one line appended per
   pass by the engine. Summarize it for the user: total passes run,
   whether it stopped due to convergence or the pass cap, findings closed,
   findings escalated (reopened past `max_reopens`), and anything left
   open.

## What NOT to do

- Do not run more than `max_passes` passes in one invocation, even if the
  user asks you to "just keep going" — a fresh invocation (a new call to
  this skill) is how they get more passes; `plan-next-pass` will refuse
  once the cap is hit regardless of what you're asked.
- Do not dispatch `confab-remediator` for an `assertion_audit` finding or
  a non-`excessive-tool-grant` `agentic_reliability` finding under any
  framing — the remediation-scope script refuses to open a scope for
  these, and the `PreToolUse` hook refuses the edit even if you tried to
  route around the scope step.
- Do not treat a `"blocked"` remediator outcome as a failure to retry
  immediately — record it as `"blocked"` and let it surface as an open
  finding for the next pass or the user's manual attention.
