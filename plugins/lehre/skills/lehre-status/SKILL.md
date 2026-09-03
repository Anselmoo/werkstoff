---
name: lehre-status
description: "Use to report where a lehre run currently stands — which units are validated, blocked or ready, how many rules are in force, and what is denied at write time right now. Trigger on 'lehre status', 'where are we', 'what's blocked', 'what can I build next', or when resuming work on a repository that already has a .lehre directory. Read-only."
---

Report the current state. Writes nothing, decides nothing.

## Steps

1. **Read the real state, never remember it.**

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lehre_cli.py" status --json
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lehre_cli.py" validate
   ```

   If either exits non-zero, report that verbatim and stop — a status built on
   an unusable ruleset is a status of nothing.

2. **Say what is denied right now**, in terms of paths a user would recognise,
   not rule ids. "A write to `src/cli/*` is refused" is actionable; "unit `cli`
   is blocked" needs a second lookup.

3. **Name the one next action.** Not a menu — the single skill that moves the
   project forward from exactly this state.

4. **Report a stale brief.** If `LEHRE_BRIEF.md` exists with
   `status: awaiting-approval`, say so; work is stopped at a gate that may have
   been forgotten rather than declined.

5. **Offer the doctrine map** when the doctrine has more than a couple of rules,
   or whenever the blocking count and the denied-at-write-time count differ —
   that gap is the thing the map exists to make visible, and it is easy to miss
   in a text summary:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/build_doctrine_html.py" . \
       --template "${CLAUDE_PLUGIN_ROOT}/assets/doctrine-viewer.html" \
       --tokens "${CLAUDE_PLUGIN_ROOT}/assets/tokens.css"
   ```

   Writes `.lehre/DOCTRINE_MAP.html` (and `.lehre/doctrine.json`). It reads only
   the ruleset already on disk and re-derives nothing. Tell the user to open it
   and click a node in the enforcement flow to filter the rule table.

## Output format

```
mode greenfield    rules 9 (5 blocking, 4 denied at write time)    guard ACTIVE

  [x] contracts    validated
  [x] adapters     validated
  [ ] domain       ready
  [ ] writer       ready
  [ ] cli          blocked by domain, writer

denied at write time right now
  src/cli/*        — cli depends on domain and writer, neither validated

next: lehre-conform domain    (domain and writer are independent — either first,
                               or both in parallel)
```

## Rules

- **Never infer state from the conversation.** The scripts are the source of
  truth; a session's memory of what was validated is not.
- **Never offer to close a unit from here.** Only `lehre-validate` closes units.
