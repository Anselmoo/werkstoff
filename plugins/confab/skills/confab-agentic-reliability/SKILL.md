---
name: confab-agentic-reliability
description: "Use when the user asks to audit this plugin repository's own skill, agent, or workflow definitions for agentic-loop reliability defects, wants to check for unbounded retries, missing escalation paths, unwired Find/Verify phases, or excessive tool grants, or asks 'is our own agent design safe'. Verification runs by default and only skips if the user explicitly says skip_verification. Findings fall into exactly four categories."
---

Audit this repository's own `skills/`, `agents/`, `commands/`, and
`workflows/` files for four specific agentic-loop reliability defect
categories: `unbounded-retry`, `no-escalation-path`,
`find-no-verify-wiring`, `excessive-tool-grant`. These four categories are
fixed — never report a fifth category, and never rename one.

## Steps

1. Determine `repo_root` and the set of skill/agent/workflow files to
   scan (default: everything under `skills/`, `agents/`, `commands/`,
   `workflows/`). Determine `skip_verification`: **default `false`**,
   same rule as `confab-contract-drift` — only `true` on an explicit user
   request.
2. Dispatch the `agentic-reliability-auditor` agent in **Find mode**
   over those files. Ask for `{"findings": [...]}` (category must be one
   of the four above) plus, separately, any trivial-scope exceptions it
   noticed (a broad-looking tool grant on a genuinely trivial skill) as
   `{"exceptions": [{"evidence": "...", "reason": "..."}]}`. Write both to
   scratch files.
3. Unless `skip_verification` is `true`: dispatch the
   `agentic-reliability-auditor` agent again in **Verify mode**,
   independently re-checking each Find-phase finding against the actual
   file. Write `{"findings": [{"evidence": "...", "confirmed": true|false}, ...]}`.
4. Run:
   ```
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/agentic_reliability.py" <repo_root> \
       --find-json <path-from-step-2> \
       [--verify-json <path-from-step-3>] \
       [--skip-verification] \
       [--trivial-exceptions-json <path-from-step-2>]
   ```
   The script rejects any finding whose category isn't one of the four,
   forces `fixability: "advisory"` on every category except
   `excessive-tool-grant`, and writes
   `analysis/confab/reports/AGENTIC_RELIABILITY.md` (grouped into four sections,
   one per category, plus a separate trivial-exceptions section) and
   `analysis/confab/agentic_reliability_summary.json`.
5. Report the per-category finding counts to the user. Call out
   `excessive-tool-grant` findings specifically as "auto-fixable via
   `confab-cycle` in fix mode" since that's the only category
   `confab-remediator` is allowed to touch.

## What NOT to do

- Do not fold a trivial-scope exception into the findings table — it has
  its own report section precisely so it doesn't inflate the finding
  count.
- Do not mark any category other than `excessive-tool-grant` as
  `fixability: "fixable"` — the writer script rejects it, but don't ask
  the agent to produce it in the first place.
