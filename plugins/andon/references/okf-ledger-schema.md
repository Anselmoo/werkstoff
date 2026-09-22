# OKF ledger schema

The andon ledger is a directory of markdown files with YAML frontmatter
("OKF docs"). This document is the human-readable description of the schema
that `scripts/andon_core.py`'s `validate_doc()` **enforces mechanically** on
every write -- this file explains the shape; the script is what actually
rejects a bad doc. If the two ever disagree, the script is authoritative.

## Contents

- Settings file: `.claude/andon.local.md`
- Doc types
- Tags
- Cross-links
- `log.md`

## Settings file: `.claude/andon.local.md`

Optional. YAML frontmatter, no required fields (every field has a documented
default). Read by every andon skill via `andon_core.py load-settings`.

| Field | Default | Meaning |
|---|---|---|
| `enabled` | `true` | `false` halts every andon skill immediately. |
| `output_dir` | `analysis/andon` | Where `PREFLIGHT.md`, etc. live. |
| `ledger_dir` | `analysis/andon/ledger` | Where the OKF ledger (`stages/`, `gaps/`, `evidence/`, `log.md`) lives, plus the rendered `ANDON_BOARD.html`. |
| `authorization_level` | `local+reversible` | Ceiling for auto-advancing past a proposal's blast radius. |
| `skip_verification` | `false` | If `true`, skips the adversarial re-verification pass where a skill offers one. |
| `gap_source` | `self-scan` | `self-scan` or `befund-brief` (ingest mode). |
| `befund_output_dir` | `analysis/befund` | Where ingest mode reads `MODERNIZATION_BRIEF.md` from. |
| `house_rules_path` | `.claude/house-rules.md` | Where `andon-propose` looks for repo conventions. |

## Doc types

Every OKF doc's frontmatter has a required `type` field: `stage`, `gap`, or
`evidence`. Beyond `type`, the fields below are **required, first-class
keys** -- never buried in prose, never inferred, never defaulted by the
writer. A doc missing one of these is rejected at write time, not silently
patched.

### `stage` doc (`stages/<slug>.md`)

- `title` (str), `order` (int) -- stage's position in the stream.
- `confidence` -- one of `befund-backed`, `heuristic`, `single-package`.
- Optional: `description`.

### `gap` doc (`gaps/<slug>.md`)

- `title` (str), `stage` (str, which stage this gap belongs to).
- `kind` -- exactly one of `bug`, `feature`, `wire`.
- `status` -- `open` or `closed`. `closed` additionally requires
  `resolved_by` (a `[[evidence/<slug>]]` wiki-link).
- `blast_radius` -- required once a `proposal` field is present: exactly one
  of `local+reversible`, `hard-to-reverse`, `shared-state-visible`.
- Optional: `on_constraint` (bool), `proposal` (object).

Example (`gaps/ingest-retry-storm-on-429.md`):

```markdown
---
type: gap
title: "ingest retries a 429 immediately, with no backoff"
stage: ingest
kind: bug
status: open
blast_radius: local+reversible
proposal: {"summary": "Add exponential backoff with jitter to the partner-feed fetcher.", "touches": ["ingest/fetch.py"]}
tags:
  - kind:bug
  - status:open
  - blast-radius:local+reversible
---

Contained entirely inside the fetcher and trivially revertible -- the reason
this one is `local+reversible` while the provenance gap two stages down is
not.
```

### `evidence` doc (`evidence/<slug>.md`)

- `title` (str), `wire` (str, `from-stage->to-stage`).
- `strategy` -- exactly one of `a` through `g`.
- `verdict` -- exactly one of `green`, `red`, `unknown`.
- `tier` -- required (1, 2, or 3) **only** when `strategy == e`; forbidden
  otherwise.
- `tier_ceiling` -- required (1 or 2) **only** when `strategy == e`; forbidden
  otherwise. This is `route_wire()`'s own output (`scripts/andon_core.py`),
  copied onto the doc rather than defaulted: it records whether the run that
  produced this evidence actually had a real structural index
  (`available_lsp_or_index`) available. Ceiling 1 means Tier 1 (a real
  Kythe/SCIP/LSIF query) was reachable; ceiling 2 means it was not, so `tier`
  is capped at 2 (AST/grep) regardless of what the evidence itself claims.
  `validate_doc()` refuses a `tier` stronger than its own run's `tier_ceiling`
  (`SCHEMA_TIER_ABOVE_CEILING`) -- without an index there was no Tier 1 query
  to have performed, so an index-less run cannot claim the one non-overridable
  stop condition (see `references/andon-rule.md`, condition 3).
- `non_overridable` -- required `true` when `tier == 1` and the index query
  contradicts the claimed edge; this is the andon rule's one non-overridable
  stop condition.
- Optional: `lane` -- one of `fast`, `slow`. Not currently validated; used
  only to emit the `lane:` tag.

## Tags

Tags are derived automatically from the first-class fields above (never
hand-authored separately, to avoid the tag and the field drifting apart):
`kind:bug|feature|wire`, `status:open|closed`,
`blast-radius:local+reversible|hard-to-reverse|shared-state-visible`,
`strategy:a`-`g`, `tier:1`-`3`, `lane:fast|slow`. All kebab-case.

## Cross-links

Use `[[relative/path/without/extension]]` wiki-link syntax, e.g.
`resolved_by: "[[evidence/stage-a-stage-b-2024-01-01]]"`.

## `retired/` directory (`retired/gaps/<slug>.md`, `retired/evidence/<slug>.md`)

Not a doc type of its own -- a retired doc is a gap or evidence record moved
out of `gaps/` or `evidence/` into the matching subdirectory under
`retired/`, unchanged otherwise. `andon_core.py retire` is the only writer:
it validates write-scope, moves the file with `os.replace`, and appends a
`retire` entry to `log.md` recording `kind`, `slug`, and `reason`.

This exists because a gap or evidence doc can go stale without anything in
the schema saying so -- a gap closed by a later re-verify whose evidence doc
still sits in `evidence/` recording its old `red`/`unknown` verdict, or a
duplicate/mis-filed record nobody wants gating anything. Editing `status` or
`verdict` in place would rewrite ledger history the append-only design is
built to avoid, so `retire` moves the doc instead.

**Why this stops the PreToolUse hook from gating on it, without teaching the
hook a fourth status:** `_list_md()` in `hooks/andon_enforce.py`'s
`stop_reason()` only ever walks `ledger_dir/gaps` and `ledger_dir/evidence` --
never `ledger_dir/retired` -- so a retired record is excluded from every stop
condition the same way a nonexistent one would be. `read_all_docs()` and
`render_board()` in `andon_core.py` are the same: neither walks `retired/`,
so a retired doc also disappears from `andon-status`'s board.

## `log.md`

Append-only. Never rewritten -- `andon_core.py append_log_entry()` opens it
in append mode only, and the PreToolUse hook independently refuses any
`Write`/`Edit` that would overwrite or edit it in place. Four entry kinds:
`pass`, `cycle-converged`, `sub-cycle`, `retire`, each with its own required
fields (see `append_log_entry`'s `REQUIRED_LOG_FIELDS`).
