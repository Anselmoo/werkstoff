# Extraction reliability grading

Grade every reference **before** decoding it, and carry the grade through every Design
Card that cites it. Without this, `decode` produces numbers with invented precision —
and once a number is written down, nothing distinguishes a measurement from a guess.

The thing being graded is not the reference's quality. It is **how much the extraction
method can support**. A superb design system read off a screenshot is still grade C.

| Grade | Source | What a value from it supports |
|---|---|---|
| **A** | Published guidelines, a design-token file, a documented spec, the user's own source material | Values usable as stated |
| **B** | Declared CSS from a fetched page | Usable as **ratios and relations**, not as absolutes |
| **C** | Screenshot measurement, visual estimate, a value read off an image | **Direction only.** Never a token value on its own |

## Why B is not A

A live page yields *declared* CSS, not rendered result. `font-size: 1.0625rem` tells you
the ratio to the root; it does not tell you the computed pixel size in the context you
saw, and it says nothing about what the layout engine did with it. Cascade, media
queries, container queries and user-agent defaults all sit between the declaration and
the pixels.

So a grade-B reference supports "the body-to-heading ratio is 1:1.9" and does not
support "body text is 17px".

## Why C exists rather than being rejected outright

Some of the most-cited systems cannot be read any other way. Apple's spacing lives in
computed layout boxes, not in a stylesheet anyone can fetch. Refusing grade C would mean
refusing the reference; pretending it is grade B would mean inventing precision. Grade C
keeps it usable for the thing it can honestly support — **direction** — and blocks the
thing it cannot.

## Secondary sources — a third party's description of someone else's system

A growing class of reference is neither the vendor's own guidelines nor a page you
measured: it is **somebody else's written interpretation of a third party's design
system**. Curated `DESIGN.md` collections are the current example — a file describing
"the Apple design system" that Apple did not write.

These are legitimate input. They are *not* grade A, and grading them A because they are
published is the trap. A secondary source underwrites **"this is one documented
interpretation"**, never **"this is what that vendor does"**.

So a secondary reference carries two extra fields and one ceiling:

- `secondary: true`
- `describes: <the system it interprets>` — naming whose system, so the claim's real
  subject is visible
- **ceiling: grade B.** Usable as ratios, relations and direction. A card that asserts
  something *about the described system* as fact needs the primary source, and says so.

The distinction is the same one this whole phase rests on. "VoltAgent's DESIGN.md states
a 4px base unit for Apple" is a measurement about a document. "Apple uses a 4px base
unit" is a claim about Apple, and the document cannot carry it.

Check the collection's own licence before reproducing anything from it — a curated
description is a copyrightable work in its own right, independent of whatever it
describes. See `rights-grading.md`.

## The rule that has teeth

> A Design Card that would set a token from a grade-C source **alone** is rejected, and
> surfaced as an open question rather than silently rounded into a number.

Two escapes from that, both legitimate:

- **Corroborate.** A grade-C observation confirmed by a grade-A or grade-B source sets
  the token on the strength of the better source, and the card cites both.
- **Promote by measuring.** If the value can be computed rather than eyeballed —
  contrast, a ratio between two measured lengths — compute it with a script and the
  result is a measurement, not an estimate. `scripts/contrast.py` exists for exactly
  this: a contrast ratio is arithmetic, so it is never graded C.

## What the grade does downstream

- `decode` — every Design Card line carries source, selector-or-page-reference, and grade.
- `name` — a rule whose only evidence is grade C is stated as a *direction*, never as a
  numeric rule.
- `validate_tokens.py` — refuses a token whose sole provenance is grade C. This is a
  script check, not a judgement call, so it cannot be talked out of.
- `brief` — lists every grade-C-only finding as an open question the human must settle.

## Related

Reliability is **not** rights. A published guideline under a NoDerivatives licence is
grade A here and R3 in `rights-grading.md` at the same time: fully trustworthy as a
source of values, and forbidden as a source of reproduced text. Record both.
