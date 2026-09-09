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
| `gap_source` | `self-scan` | `self-scan` or `self-assess-brief` (ingest mode). |
| `self_assess_output_dir` | `analysis/self-assess` | Where ingest mode reads `MODERNIZATION_BRIEF.md` from. |
| `house_rules_path` | `.claude/house-rules.md` | Where `andon-propose` looks for repo conventions. |

## Doc types

Every OKF doc's frontmatter has a required `type` field: `stage`, `gap`, or
`evidence`. Beyond `type`, the fields below are **required, first-class
keys** -- never buried in prose, never inferred, never defaulted by the
writer. A doc missing one of these is rejected at write time, not silently
patched.

### `stage` doc (`stages/<slug>.md`)

- `title` (str), `order` (int) -- stage's position in the stream.
- `confidence` -- one of `self-assess-backed`, `heuristic`, `single-package`.
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

## `log.md`

Append-only. Never rewritten -- `andon_core.py append_log_entry()` opens it
in append mode only, and the PreToolUse hook independently refuses any
`Write`/`Edit` that would overwrite or edit it in place. Three entry kinds:
`pass`, `cycle-converged`, `sub-cycle`, each with its own required fields
(see `append_log_entry`'s `REQUIRED_LOG_FIELDS`).
