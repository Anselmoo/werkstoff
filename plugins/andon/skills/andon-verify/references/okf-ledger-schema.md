# OKF ledger schema

The concrete frontmatter schema `andon-loop` uses for the OKF (Open
Knowledge Format) bundle it owns as the plugin's ledger. Spec reference:
https://github.com/GoogleCloudPlatform/knowledge-catalog/tree/main/okf
(v0.1). The format — plain markdown files with YAML frontmatter,
organized as a directory tree — is stable and simple enough to implement
**natively, with no external dependency**. The reference-agent/visualizer
tooling in that repo is explicitly proof-of-concept; this plugin does not
take a hard dependency on it (see `andon-status/SKILL.md` for the
optional, best-effort use of it).

`andon-loop` is the ledger's owner (init/resume, writes new docs, updates
frontmatter). `andon-verify`'s strategies each produce the content for one
`type: evidence` doc per proof attempt, but never write it directly —
they return structured results that `andon-loop` persists, the same
separation self-assess/quality keep between analysis agents (which never
write files) and the orchestrating skill (which does).

## Directory layout

```
<ledger_dir>/                    # default analysis/andon/ledger
├── log.md                       # OKF reserved filename — chronological pass/cycle history
├── stages/
│   ├── <stage-slug>.md          # type: stage
│   └── ...
├── gaps/
│   ├── <gap-id>.md              # type: gap
│   └── ...
└── evidence/
    ├── <evidence-id>.md         # type: evidence
    └── ...
```

`<stage-slug>` is the stage name from topology detection, kebab-cased.
`<gap-id>` and `<evidence-id>` are short, stable, content-addressed-ish
slugs (`<stage-slug>-<short-hash-or-counter>`) — stable across resumed
sessions so links don't rot.

## Required OKF frontmatter key

Every concept doc has exactly one **required** field per the OKF spec:

- `type` — one of `stage`, `gap`, `evidence` in this plugin's usage.

## Recommended OKF frontmatter keys (used by this plugin)

- `title` — human-readable name.
- `description` — one-line summary.
- `resource` — for `evidence` docs, a path/URL to the underlying artifact
  (e.g. a test file, a transcript, a report path) when one exists outside
  the doc itself.
- `tags` — a list; this plugin's own usage below.
- `timestamp` — ISO 8601, when the doc was created or last updated.

## Per-type schema (this plugin's concrete usage)

### `type: stage`

```yaml
---
type: stage
title: "<stage name>"
description: "<one line — what this stage is/does>"
tags: ["lane:fast" | "lane:slow"]
timestamp: "<ISO 8601>"
---

## Stage detail

- Detected via: self-assess:stage-mapper | built-in heuristic (reduced confidence)
- Outgoing wires: <list of stage-slugs this stage feeds>
- Incoming wires: <list of stage-slugs that feed this stage>
```

`tags` carries the fast/slow lane classification (see
`andon-vocabulary.md`) — a stage can carry both tags if it has wires in
both lanes; tag the *wire* more precisely where the granularity matters
(a future schema revision could move lane tagging to a `wires` field
inside the stage doc's body — v0.1 keeps it at stage granularity for
simplicity and revisits only if a real repo's mixed-lane stages make
that too coarse).

### `type: gap`

```yaml
---
type: gap
title: "<short gap description>"
description: "<what's broken/missing/unproven>"
tags: ["kind:bug" | "kind:feature" | "kind:wire", "status:open" | "status:closed",
       "blast-radius:local+reversible" | "blast-radius:hard-to-reverse" | "blast-radius:shared-state-visible"]
timestamp: "<ISO 8601>"
---

## Gap detail

- Stage: [[stages/<stage-slug>]]
- On constraint: true | false
- Resolved by: [[evidence/<evidence-id>]]   ← only present once closed; this is the
  link that gives the free reverse-link "cited by" index — evidence docs
  don't need to separately declare which gap they resolved, `andon-status`
  derives "cited by" by scanning gap docs for `evidence/` links.
- Proposal: <andon-propose's output — fix description, files touched,
  chosen verification strategy>
```

### `type: evidence`

```yaml
---
type: evidence
title: "<short evidence description>"
description: "<what this evidence proves or refutes>"
resource: "<path to underlying artifact, if any — a test file, transcript, report>"
tags: ["strategy:a" | "strategy:b" | ... | "strategy:g",
       "tier:1" | "tier:2" | "tier:3"]   # tier tag only present for strategy e
timestamp: "<ISO 8601>"
---

## Evidence detail

- Wire: <from-stage> -> <to-stage>
- Verdict: green | red
- Strategy detail: <strategy-specific summary — e.g. for b, the V&V
  technique used and trust-ledger entry; for e, the tier and the tool
  that produced it; for g, which original evidence doc this audits>
- Non-overridable: true | false   ← true only for strategy e Tier 1 hits,
  per the andon rule's stop condition 3
```

The `tags` field is how `andon-status` and `andon-loop` filter/aggregate
without parsing prose — always machine-checkable, never left to
free-text inference.

## Cross-linking convention

Use `[[relative/path/without/extension]]` wiki-link style inside the
markdown body for stage ↔ gap ↔ evidence references (readable both as
plain markdown and as a link by any OKF-aware tool). `andon-status`'s
native renderer resolves these by string-matching, not by requiring a
particular markdown-link-parsing library — keep the convention exactly
as shown so that stays true.

## `log.md`

OKF's reserved filename for a bundle's own narrative log. This plugin
uses it for the plugin's pass/cycle chronological history — one entry per
pass close or cycle close, appended (never rewritten), in the same shape
as `andon-loop`'s cycle-report format:

```markdown
## Pass 3 (cycle 1) — 2026-07-16T14:02:00Z
Stage: web  ·  Wire: bench -> web  ·  Gap: [[gaps/web-a1b2]]
Strategy: a (tribunal)  ·  Verdict: green
Advanced to: next wire

## Cycle 1 converged after 3 passes — 2026-07-16T15:40:00Z
Stream: crate -> core -> bench -> web (all wires green)
Sub-cycles: 1 backtrack (bench -> json schema change)
```

Never invent a second, competing history file — `log.md` is the single
chronological record.
