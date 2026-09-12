---
name: matrize-decode
description: "Use to MEASURE what collected references actually do — type scale as ratios rather than px, spacing as a base unit plus steps, colour as roles before values, radii as a series, motion as duration and easing classes, density — emitting one Design Card per finding with its source, its selector-or-page reference and its reliability grade. Trigger on 'decode these references', 'what do these references actually do', 'measure the type scale', 'matrize decode'. Measures and cites only; it never names, justifies or interprets — that is matrize-name — and a card is not accepted until a second agent re-derives it from the cited source."
---

Measure. Do not interpret. The whole value of this phase is that a later reader can tell
a measurement from a claim, and that distinction survives only if the two are never
written by the same pass.

## Extract relations, not absolutes

A design system that records `font-size: 17px` has recorded one page. A system that
records `body : heading = 1 : 1.9` has recorded a decision. So:

- **type** — a scale as ratios against a base, plus the base itself as a separate finding
- **spacing** — a base unit and the integer steps actually used, not the pixel list
- **colour** — **roles before values**. What is the ink, the paper, the hairline, the
  single dominant action colour? Only then, what are they set to
- **radii** — a series and its progression, not five unrelated numbers
- **motion** — duration and easing *classes*, with the DTCG types they map to
- **density** — measure in characters, line-height, and the ratio of gap to text size

Colour roles matter more than they look. A reference whose palette resists being named
in roles usually has no system — that is itself a finding, and worth stating.

## Every card carries its evidence

One Design Card per finding, in the exact shape of
`${CLAUDE_PLUGIN_ROOT}/references/design-card-schema.md`. Never restate the schema here
or in an agent prompt; it lives in one place so it cannot drift into two.

Non-negotiable per card: **source**, **selector-or-page-reference**, **reliability
grade**, a confidence sentence, and its **outgoing edges**. A card that cannot cite where
it was read is not a card.

**Edges are written here, not inferred later.** Each card records `reference -> card` and,
when it sets one, `card -> token`, each edge carrying the grade it was derived under. This
is a schema obligation on this phase, not a feature of a viewer: reconstructing the graph
by matching values across files merges roles that happen to share a value, which is the
defect class the graph exists to expose. See the schema for the two real cases that
settled it.

The rule with teeth, mirroring the "a comment is not a rule" discipline that makes
citation-backed extraction falsifiable elsewhere in this workshop:

> **A value supported solely by a screenshot is not a token.**

A card that would set a token from a grade-C source alone is rejected and surfaced as an
open question. `scripts/validate_tokens.py` enforces it, so it is not a judgement call.

## What a reference actually yields, per dimension

Before measuring a dimension, read its vocabulary file under
`${CLAUDE_PLUGIN_ROOT}/references/vocabulary/`. Each one ends with **Decoding notes**: what
that dimension yields from a reference and at what grade, written per term rather than
per reference.

They carry findings that are cheaper to reuse than to rediscover. The base unit is
inferable at grade B by taking the greatest common divisor of every observed spacing
value — *and if the GCD is 1, there is no grid, which is itself the finding*. A baseline
grid is grade C at best because it lives in computed line boxes and is rarely declared.
Spring parameters are grade C or absent, because unless expressed through `linear()` they
live in JavaScript. Timing by eye is grade C, always.

Record ratios, not absolutes: "section spacing is 2× card padding" survives a rescale
and "48px" does not.

## Name the concept, and respect its ceiling

Every card carries `**Concept:**` — the vocabulary term it is a measurement *of*, plus the
dimension that defines it. It cannot be derived from the value or from the CSS name:
matching custom-property names against the vocabulary binds 1 of this repository's 50
declarations, because names are roles and the vocabulary names concepts.

Some concepts carry a **written grade ceiling** in
`${CLAUDE_PLUGIN_ROOT}/references/vocabulary/README.md`, taken from the Decoding notes. A
card claiming a better grade is rejected by `V-VOCAB-GRADE-CEILING`, whatever its
confidence says — a baseline grid is grade C at best, a growth rule is not recoverable
from a reference at all.

A concept the vocabulary does not name is allowed only as a declared extension carrying
its reason. Coining a near-synonym instead is the failure mode: it looks like coverage and
is a second name for something that already has one.

## Fan out, with a breaker

Dispatch one `reference-decoder` per reference. First batch 4, then ×2, then ×4, hard
cap 16.

The **circuit breaker** trips when accepted cards fall strictly below two-thirds of
*measurable* cards, judged **per batch, never cumulatively** — a cumulative rate lets
healthy early batches mask a batch that has started failing, and fires one expensive
batch too late. A reference that could not be fetched or read at all is **excluded from
the denominator** rather than counted as a rejection: it says nothing about whether the
rubric is right.

When the breaker trips, revise the rubric. Do not launch more agents at it.

## Verify by re-derivation, not by review

Every card is re-derived by a `decode-referee` that sees the **cited source and the
claim**, never the first agent's reasoning or summary. An agent asked "is this right?"
while holding the argument for it will agree. An agent asked "what does this source
actually say?" will not.

A card the referee cannot reproduce is dropped, with the disagreement recorded.

## Write DECODE.md

Agents return structured results; **this skill writes the file**. No fan-out agent holds
`Write` or `Edit`, because reference content is untrusted input and that separation is
the containment boundary, not a formality.

Lead with a summary table (id, what, role, reliability, source), then the cards grouped
by dimension, then a final **"Findings that cannot set a token"** section listing every
grade-C-only result with the question a human must answer.

## Resources

- `references/design-card-schema.md` — the single definition of a Design Card. Mandatory
  read before writing one.
- `references/reliability-grading.md` — what each grade licenses a card to claim.
- `references/vocabulary/*.md` — per-dimension terms, confused pairs, and the **Decoding
  notes** that say what each dimension yields and at what grade. Read the file for the
  dimension before measuring it.
