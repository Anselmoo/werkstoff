# Design Card schema

One card per measured finding. This file is the **only** definition of the shape —
skills and agents reference it by name rather than restating it, so it cannot drift into
two versions that disagree.

A Design Card records a **measurement**, not a judgement. If a sentence in a card could
be argued with on taste, it belongs in `LEXIKON.md` instead.

## Contents

- [The shape](#the-shape) — two worked cards, one that sets a token and one that cannot
- [Edges are written, never reconstructed](#edges-are-written-never-reconstructed) — I8,
  and the two real cases that settled it
- [Field rules](#field-rules)
- [The rule that makes a card falsifiable](#the-rule-that-makes-a-card-falsifiable)

## The shape

```
### CARD-014: body-to-heading type ratio
**Dimension:** type | spacing | colour | radius | motion | density | content
**Reference:** hig-web
**Source:** references/hig-web/type.css — selector `:root`, lines 12-19
**Method:** declared CSS from a fetched page
**Reliability:** B — declared, not rendered; usable as a ratio, not as an absolute
**Rights:** R3 — all rights reserved; values measured and cited, nothing reproduced
**Concept:** Type scale (typography) — kind `token`
**Measured:** body 1.0625rem, h2 2rem, h1 2.5rem against a 1rem root
**As a relation:** body : h2 : h1 = 1 : 1.88 : 2.35, stepping by ~1.25 between levels
**Holds across:** 4 of 5 collected pages; the marketing page steps by 1.33 instead
**Confidence:** High — four independent pages agree, and the outlier is a different template
**Sets a token:** yes — `type.scale.ratio`
**Edges:**
  - hig-web -> CARD-014 (grade B)
  - CARD-014 -> type.scale.ratio (grade B)
```

And one that does not clear the bar, which is just as important to write down:

```
### CARD-021: card corner radius
**Dimension:** radius
**Reference:** competitor-app
**Source:** references/competitor-app/home.png — measured on screen at 2x
**Method:** screenshot measurement
**Reliability:** C — read off an image; direction only
**Rights:** R3 — screenshot of a proprietary interface
**Concept:** Corner radius (icon-system) — kind `token`
**Measured:** approximately 12-14px at 2x, so ~6-7px at 1x
**As a relation:** roughly 0.4× the 16px base unit; the series looks like 1×/2×/3× of ~6px
**Holds across:** 1 page
**Confidence:** Low — a single screenshot, and antialiasing makes ±2px unresolvable
**Sets a token:** NO — grade-C evidence alone. Open question: is the radius series
  derived from the spacing base, or independent? Needs a second source or a decision.
**Edges:**
  - competitor-app -> CARD-021 (grade C)
```

## Every card names the concept it measured

`**Concept:**` is the vocabulary term the card is a measurement *of*, plus the dimension
file that defines it. It is not decoration and it is not a synonym for the token name:
`--space-1` is a **role**, `Spacing step` is the **concept**, and the vocabulary is the
registry of concepts.

Measured against this repository's own 50 declarations, matching a CSS custom-property
name to a vocabulary term binds **one**. So the concept cannot be derived from the name —
it is a judgement the decoder makes and the referee re-derives, exactly like the
measurement itself.

What the concept buys, mechanically, is in `scripts/validate_tokens.py`:

| the vocabulary says | consequence |
|---|---|
| kind `token` | may live in `tokens.json` |
| kind `derived` | computed from tokens; storing it makes a second copy that drifts (`V-VOCAB-NOT-A-TOKEN`) |
| kind `property` | observed, never stored (`V-VOCAB-NOT-A-TOKEN`) |
| kind `rule` | a lexicon entry, and it needs an anti-rule (`V-VOCAB-RULE-NO-ANTIRULE`) |
| a written grade ceiling | the card may not claim a better grade (`V-VOCAB-GRADE-CEILING`) |
| no such term | blocked, unless the card declares the extension and says why (`V-VOCAB-UNKNOWN`) |

A concept the vocabulary does not name is allowed, and it is never silent:

```
**Concept:** Density bias — NOT IN THE VOCABULARY
**Extends:** no vocabulary term names a per-surface density offset; grid-and-spacing.md
  has `Density` as a global multiplier, which this is not
```

`matrize-status` reports every declared extension. They are the vocabulary's backlog, not
a loophole.

## Edges are written, never reconstructed

Every card records its **outgoing edges** explicitly — `reference -> card` and, when it
sets one, `card -> token` — and each edge carries the reliability grade it was derived
under. The provenance renderer reads these. It never infers the graph by matching values
across `DECODE.md` and `tokens.json`.

That is not a precaution. Reconstruction was tested against a real 50-declaration token
file before this rule was written, and it failed twice on the first try:

- **Two roles, one value.** `4px` is both `--space-1` and `--radius-sm`; `8px` is both
  `--space-2` and `--radius-panel`. Value-matching merges a spacing role into a radius
  role.
- **Three roles, one source.** `--cat-1`, `--accent` and `--diverging-cool` all resolve
  to `var(--silica)`. A reconstructed graph shows one node where there are three
  dependents — so it answers *"what breaks if I change this?"* with **one** when the
  truth is **three**, which is the single question the graph exists to answer.

A card that sets a token and records no `card -> token` edge is rejected by
`validate_tokens.py`. The cost is one field per card; the alternative is a graph that is
confidently wrong in exactly the cases that matter.

**Grade per edge, not per card.** A card corroborated by a grade-A source but reaching
its token through a grade-C inference has an A edge and a C edge, and the renderer draws
the C edge dashed — reusing the `'4,3'` dash that already means *unproven* in three of
this repo's viewers.

## Field rules

- **Source** must name a *location*, not a document. `references/x/type.css` is not a
  source; `references/x/type.css — selector :root, lines 12-19` is. For a page-based
  reference, name the page and the element. For an image, name the image and how it was
  measured.
- **Reliability** and **Rights** are independent. See `reliability-grading.md` and
  `rights-grading.md`. A card is expected to carry mismatched grades — A/R3 is the
  commonest pair for a published system.
- **As a relation** is mandatory and is the field that makes the card portable. A card
  with only absolutes has recorded one rendering of one page.
- **Holds across** is how a single observation is prevented from becoming a system rule.
  One page is not a pattern; say "1 page" when that is the truth.
- **Confidence** is about the *measurement*, not about whether the design is good.
- **Sets a token** is a yes/no with a consequence. `scripts/validate_tokens.py` refuses
  a token whose sole provenance is grade C, so a card claiming `yes` on grade-C evidence
  alone fails a script check rather than a review.

## The rule that makes a card falsifiable

> **A value supported solely by a screenshot is not a token.**

The corresponding discipline on the interpretation side is that a card must be
reproducible: a `decode-referee` is given the **cited source and the claim**, never the
authoring agent's reasoning, and must arrive at the same measurement independently. A
card the referee cannot reproduce is dropped and the disagreement recorded.

That is the whole reason **Source** has to be a location. A referee cannot re-derive
from "the HIG".
