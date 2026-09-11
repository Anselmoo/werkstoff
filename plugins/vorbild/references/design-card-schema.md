# Design Card schema

One card per measured finding. This file is the **only** definition of the shape —
skills and agents reference it by name rather than restating it, so it cannot drift into
two versions that disagree.

A Design Card records a **measurement**, not a judgement. If a sentence in a card could
be argued with on taste, it belongs in `LEXIKON.md` instead.

## The shape

```
### CARD-014: body-to-heading type ratio
**Dimension:** type | spacing | colour | radius | motion | density | content
**Reference:** hig-web
**Source:** references/hig-web/type.css — selector `:root`, lines 12-19
**Method:** declared CSS from a fetched page
**Reliability:** B — declared, not rendered; usable as a ratio, not as an absolute
**Rights:** R3 — all rights reserved; values measured and cited, nothing reproduced
**Measured:** body 1.0625rem, h2 2rem, h1 2.5rem against a 1rem root
**As a relation:** body : h2 : h1 = 1 : 1.88 : 2.35, stepping by ~1.25 between levels
**Holds across:** 4 of 5 collected pages; the marketing page steps by 1.33 instead
**Confidence:** High — four independent pages agree, and the outlier is a different template
**Sets a token:** yes — `type.scale.ratio`
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
**Measured:** approximately 12-14px at 2x, so ~6-7px at 1x
**As a relation:** roughly 0.4× the 16px base unit; the series looks like 1×/2×/3× of ~6px
**Holds across:** 1 page
**Confidence:** Low — a single screenshot, and antialiasing makes ±2px unresolvable
**Sets a token:** NO — grade-C evidence alone. Open question: is the radius series
  derived from the spacing base, or independent? Needs a second source or a decision.
```

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
