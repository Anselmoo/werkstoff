---
name: andon-status
description: Renders the andon board from the current OKF ledger state without running a new pass — which stages/wires are green, red, or unknown, the current cycle/pass counters, the active constraint, and the single most useful next step. Use this when the user asks "where does andon stand", "show me the andon board", "what's the current constraint", "what should andon fix next", or "andon status".
---

Report where the andon loop's ledger stands, in one screen. This is a
**read-only** skill — inspect, never modify, and never run a new pass or
gap scan (that's `andon-loop`'s job).

## 1 — Load the ledger

Read `.claude/andon.local.md` if it exists (see
`${CLAUDE_PLUGIN_ROOT}/references/settings.md`) to get `ledger_dir`
(default `analysis/andon/ledger`) and `output_dir` (default
`analysis/andon`) — `andon-loop` may be writing somewhere else if this
repo overrides it, and this skill must look in the same place or every
artifact reads as missing.

If `<ledger_dir>/log.md` does not exist, report plainly that andon has
never run in this repo and suggest `andon-preflight` then `andon-loop`
as the next steps — do not fabricate a board for a ledger that isn't
there.

Otherwise read every `stages/*.md`, `gaps/*.md`, `evidence/*.md` doc
(per the schema in `skills/andon-verify/references/okf-ledger-schema.md`)
and `log.md` in full.

## 2 — Primary rendering path: native markdown board

Always produce this path — it has no external dependency and always
works, regardless of what else is installed. Build:

- **Stream table** — one row per stage: name, outgoing wire status
  (🟢/🔴/⚪, derived from the most recent linked evidence doc for that
  wire), lane tag if present.
- **Cursor** — which stage/wire the loop is currently on (the first
  open gap doc found, in stage order; "converged, no open gaps" if none).
- **Cycle/pass counters** — parsed from `log.md`'s `## Pass N (cycle M)`
  and `## Cycle N converged` headings; report the current cycle, current
  pass within it, and total passes/cycles all-time.
- **Constraint** — the stage/wire with the most `## Sub-cycle` entries
  in `log.md` referencing it, or the stage with the oldest open gap if
  no sub-cycles have occurred yet.
- **Open gaps** — count by `kind` (`bug`/`feature`/`wire`) and by
  blast-radius tag, from `gaps/*.md` docs with `status:open`.
- **Evidence-strategy mix** — count of evidence docs by `strategy:*` tag,
  so a user can see at a glance whether the loop has been leaning on the
  tribunal for everything or actually routing across all seven
  strategies per `wire-classifier.md`.
- **Non-overridable holds** — any evidence doc with `Non-overridable:
  true` (a Tier 1 structural contradiction, andon rule condition 3) still
  linked to an open gap — surface these first, prominently, since they
  are the one stop condition a human can't adjudicate past.

Write this as `<output_dir>/ANDON_BOARD.md` and print a condensed version
in the session.

## 3 — Secondary, best-effort path: OKF reference tooling

**Optional. Never blocks or fails the primary path above.** If the OKF
reference-agent/visualizer tooling from
https://github.com/GoogleCloudPlatform/knowledge-catalog happens to be
installed and importable in this environment (e.g. a `okf` or similar
CLI resolves on `PATH`, or a Python package importable via a quick
`python3 -c "import okf"`-style probe — check, do not assume), also try
invoking its `visualize` subcommand against `<ledger_dir>` for a richer
self-contained HTML view.

- If it succeeds, mention the extra HTML output's path alongside the
  markdown board.
- If it's not installed, not importable, or the invocation errors for
  any reason, **say nothing more than a one-line, non-alarming note**
  ("OKF reference tooling not available — markdown board above is
  authoritative") and move on. This path must never raise an error the
  user has to deal with, never delay the response meaningfully, and
  never be treated as a prerequisite for a useful `andon-status` run —
  it is explicitly a proof-of-concept per that repo's own README, and
  this plugin takes no hard dependency on it.

## 4 — Verdict

End with three lines:
- **Where you are** — cycle/pass, cursor, how many wires are currently
  green vs. red vs. unknown.
- **What's blocking** — the current constraint, and any non-overridable
  hold from Section 2, or "nothing — all wires green, cycle converged."
- **Next step** — `andon-loop` to continue the current pass, or (if
  converged) the self-optimize recommendation from the last `## Cycle N
  converged` entry in `log.md`.
