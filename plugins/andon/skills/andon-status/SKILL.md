---
name: andon-status
description: "Reports the current andon board -- stream table, wire statuses, cycle/pass counters, active constraint, open gap counts, evidence-strategy mix -- without running a new pass. Use when the user asks for the current andon board, wire statuses, cycle or pass counters, the active constraint, or what to do next, without wanting a new pass run."
allowed-tools: "Read, Bash, Glob"
argument-hint: ""
---

# andon-status

Strictly read-only: inspect the ledger, never modify it, never run a new
pass. Read settings first so you look in the right place:

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/andon_core.py load-settings <repo_root>
```

Use the returned `ledger_dir` / `output_dir` for everything below.

## If the ledger has never run

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/andon_core.py render-board <repo_root> <ledger_dir>
```

If this returns `{"never_run": true}` (no `log.md` at `ledger_dir`), say so
plainly and suggest `andon-preflight` then `andon-loop` as next steps. **Do
not fabricate a board** -- an empty-looking board that implies "nothing to
do" is a different, false, message from "this has never run."

## If the ledger exists

The same `render-board` call returns everything needed, computed from the
ledger's actual files (never invented):

- `stages` and `wire_rows` (each wire's status is **derived from its latest
  linked evidence doc's verdict tag** -- green/red/unknown -- never inferred
  from anything else).
- `cursor`: the first open gap found, or `"converged"`.
- `counters`: `total_passes`, `current_cycle`, `pass_in_cycle`,
  `cycles_converged` -- parsed from `log.md`'s actual `Pass N` / `Cycle N
  converged` entries. Never invent or estimate these; if `log.md` doesn't
  mention it, the count is what the script computed, not a guess.
- `constraint`: the stage/wire with the most sub-cycle log entries, or the
  oldest open gap if none have sub-cycled yet.
- `open_gap_counts_by_kind` / `open_gap_counts_by_radius`.
- `strategy_counts`: tally by `strategy:a` through `strategy:g` tags.
- `non_overridable_holds`: any evidence doc with a Tier 1 non-overridable
  contradiction still linked to an open gap.

## Render order

1. **Non-overridable holds first, prominently.** If
   `non_overridable_holds` is non-empty, lead the board with it -- these are
   permanent blocks, not just the current bottleneck, and burying them below
   the stream table would understate their severity.
2. Stream table (stages + wire statuses).
3. Cursor, cycle/pass counters, active constraint.
4. Open gap counts by kind and blast-radius.
5. Evidence-strategy mix.

## Also write the HTML board

After the markdown board above, also render it as a self-contained HTML
dashboard -- same data `render-board` already returned, nothing re-derived:

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/build_board_html.py <repo_root> <ledger_dir> \
    --template ${CLAUDE_PLUGIN_ROOT}/assets/board-viewer.html
```

Written inside the ledger directory itself (`<ledger_dir>/ANDON_BOARD.html`),
never as a sibling of it -- andon_enforce.py's PreToolUse hook allows any
write resolving inside the ledger dir unconditionally ("the loop must always
be able to record its halt"), so this rendering step can never itself be
blocked by a stop condition. If this returns `{"never_run": true}`, skip it
silently -- the "never run" case is already handled above. Mention the
written path to the user as a bonus, but never let this step block or delay
the markdown board, which stays authoritative.

## Optional secondary path: OKF reference tooling

Best-effort only, and never allowed to block or delay the markdown board
above. If an `okf` CLI is importable, try:

```
okf visualize <ledger_dir>
```

If it succeeds, mention the HTML output path as a bonus alongside (or instead
of) the plugin's own board above. If it's absent or errors, emit one calm
line -- "OKF reference tooling not available -- markdown board above is
authoritative" -- and move on. Never let this secondary path fail the primary
one, and never spend more than one attempt on it.
