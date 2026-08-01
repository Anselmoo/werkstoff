---
description: Derive the canonical form for each divergent, undocumented, non-deprecated convention — with a provenance-tracked Pattern Card per dimension
argument-hint: <area-dir> [dimension-pattern]
---

For every in-scope dimension in `analysis/$1/consistency.json`, decide
**which existing variant becomes the canon** — or, when none deserves it,
say so plainly instead of faking a derivation. This command is the reason
`codebase-consistency` exists: the gap between "documented convention"
(someone else's job) and "version-deprecated idiom" (someone else's job)
is exactly the set of decisions made here.

If a `[dimension-pattern]` was given (`$2`), scope to matching dimensions;
otherwise cover every in-scope dimension from the scan.

## Extraction procedure — apply in this exact order, per dimension

**Step 1 — Explicit source, one more time.** `/consistency-scan` already
routed documented conventions out of scope, but re-check here against
anything written *since* the scan (a style guide committed mid-session,
an ADR merged this week). If found, this dimension is **not derived** —
report it as `documented`, cite the source, and move on. Do not produce a
Pattern Card that duplicates a written rule.

**Step 2 — Mine and weight the variants.** For each remaining dimension,
gather every site implementing each variant (from the scan's clusters),
then weight by:

- **Frequency** — raw site count per variant. The starting hypothesis.
- **Maturity** — for each variant, pull the touched files' commit
  density and review history (`git log --follow`, PR count if available).
  A variant implemented in heavily-reviewed, well-tested code outweighs
  one implemented in code nobody has touched since it was written, even
  at a lower site count — churn and review are a stronger signal of "this
  survived contact with reality" than raw frequency.
- **Recency** — a variant that's new and growing (adopted in every file
  touched in the last N commits, displacing an older one) can be the
  *intended* direction even at a minority count. Do not let sheer legacy
  volume automatically win against a variant the team is visibly migrating
  toward — but do not assume recency alone either; a recent one-off is not
  a trend. Look for **consistent, repeated** adoption in new code, not a
  single instance.

Combine these into a **candidate ranking**, not a single mechanical
formula — report the frequency split, the maturity signal, and the recency
signal separately in the Pattern Card so a human reviewing it in
`/consistency-brief` can see the actual basis, not just a score.

**Step 3 — Decide: derived, or synthesized.**

- **Clear winner** (one variant dominates on frequency, or is weaker on
  frequency but clearly winning on maturity+recency, with no serious
  countervailing signal) → mark `derived-majority`, cite the winning
  variant as canon, list every dissenting site as a divergence to close.
- **No clear winner** (close split, conflicting signals — e.g. the
  higher-frequency variant is also the oldest and least-reviewed) → do
  **not** force a pick. Mark the dimension `synthesized-new`: either
  propose a new form that resolves the conflict (grounded in something the
  repo itself signals — e.g. a recently-added dependency or interface that
  implies a direction — never an external "best practice" opinion), or
  mark it `needs-human-decision` and say so. A confident-sounding derivation
  from a genuine tie is worse than an honest "this needs a person."

## Pattern Card format

One card per dimension, in this exact format:

```
### PATTERN-NNN: <dimension name>
**Provenance:** documented | derived-majority | synthesized-new | needs-human-decision
**Canonical form:** <code example or description>
**Basis:**
  Frequency: <N of M sites, X%>
  Maturity: <what the commit/review signal showed>
  Recency: <trend direction, if any>
**Divergent sites:** <count, grouped by module, with file:line for the largest cluster>
**Blast radius:** <files, modules affected by aligning everything to this canon>
**Confidence:** High | Medium | Low — <why>
**Open question:** <only for needs-human-decision — the exact question a person must answer>
```

Write all cards to `analysis/$1/PATTERN_CARDS.md`, grouped:
- Summary table at top (ID, dimension, provenance, confidence, sites to
  align)
- Cards in full, ordered by blast radius (largest first — that's what a
  reviewer needs to see first in `/consistency-brief`)
- A final **"Needs human decision"** section listing every
  `needs-human-decision` dimension with its open question

Also write `analysis/$1/CANON.json` — the machine-readable form
`/consistency-align` executes against:

```json
{
  "area": "$1",
  "patterns": [
    {
      "id": "error-handling-style",
      "provenance": "derived-majority",
      "canonicalForm": "return Result<T,E>",
      "divergentSites": [{ "module": "shipping", "files": ["shipping/dispatch.py"], "count": 17 }],
      "confidence": "High"
    }
  ]
}
```

## Method A — Workflow orchestration (preferred when available)

If the **Workflow tool** is available in this session, use it — this
command invocation is your authorization:

```
Workflow({
  scriptPath: "${CLAUDE_PLUGIN_ROOT}/workflows/canonize.js",
  args: { area: "$1", dimensionPattern: "$2" }
})
```

This runs one **pattern-extractor** per dimension, loops additional rounds
until two consecutive rounds find no new divergent site, has an
independent **pattern-analyst** referee re-derive the maturity/recency
signal for every candidate canon before it's trusted, and runs a two-judge
panel (fidelity + basis-soundness) on every `derived-majority` card before
it can anchor `/consistency-brief`. Tell the user the agent count before
launching. On return, render `confirmedPatterns` into the two artifacts
above; report `rejectedPatterns` (candidates the referees couldn't
confirm) as a count with 1–2 examples.

## Method B — Direct subagent fan-out (fallback)

Spawn one **pattern-extractor** subagent per in-scope dimension in
parallel, running Steps 1–3 above. Then verify each candidate yourself: for
`derived-majority` cards, re-read a sample of both the winning and losing
variant's sites to confirm the frequency claim; for `synthesized-new`
cards, confirm no documented or majority signal was actually available
before accepting the synthesis.

## Present

Report: dimensions processed, split by provenance
(documented / derived-majority / synthesized-new / needs-human-decision),
and — when Method A ran — how many candidate cards the referees rejected.
Suggest `/consistency-brief $1` next.
