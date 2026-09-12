# Visual Asset Classes — reference taxonomy

A working vocabulary for naming the visual elements of a design system.

**Caveat before use.** There is no canonical industry list. DocC formally
recognises only two purposes (`icon`, `card`); Material, Fluent and Polaris each
carry their own vocabulary and disagree on boundaries. The `Established`
column below separates terms a designer will recognise unprompted from
descriptive labels that are useful but not standard. Treat the descriptive ones
as candidates for your own lexicon, not as received terminology.

**The operative column is `Origin`.** It decides what a generator can and cannot
promise:

| Origin | Meaning | What a design system can deliver |
|---|---|---|
| `derivable` | Producible from tokens and rules | The asset itself, completely |
| `drawn` | Requires authorship | The system — grid, keylines, stroke, naming — plus a seed set and a growth rule |
| `captured` | Taken from the product | Capture rules: frame, chrome, state, redaction |
| `shot` | Photographed | Direction: subject, colour temperature, crop, scrim level |

---

## Contents

- [Identity marks](#identity-marks)
- [Functional imagery](#functional-imagery)
- [Explanatory imagery](#explanatory-imagery)
- [Editorial imagery](#editorial-imagery)
- [Ambient and treatment](#ambient-and-treatment)
- [State and motion](#state-and-motion)
- [Frequently confused pairs](#frequently-confused-pairs)
- [Construction vocabulary](#construction-vocabulary)
- [Consequences for a generating system](#consequences-for-a-generating-system)

---

## Identity marks

| Class | Purpose | Established | Origin |
|---|---|---|---|
| Logo / wordmark | Entity identity | yes | drawn |
| Lockup | Mark and wordmark in a fixed spatial relation | yes | drawn |
| Monogram | Compressed identity where a full lockup will not fit | yes | drawn |
| App icon / favicon | Identity at the smallest legible size; own grid and rules | yes | drawn |
| Avatar | Identity of a person or account | yes | captured |

## Functional imagery

| Class | Purpose | Established | Origin |
|---|---|---|---|
| Icon | Names an action or object inside a control; grid-bound, usually monochrome | yes | drawn |
| Glyph | The shape itself, as distinct from the role an icon plays | yes | drawn |
| Icon badge | Icon in a coloured container, carrying status | descriptive | derivable from icon + token |
| Indicator / dot | Presence or state, no semantic shape | descriptive | derivable |

## Explanatory imagery

| Class | Purpose | Established | Origin |
|---|---|---|---|
| Diagram | Shows relationships text cannot carry | yes | drawn or generated |
| Schematic | Technical structure, dimensioned | yes | drawn |
| Chart | Quantities against a scale | yes | derivable from data |
| Screenshot | The actual product surface, as evidence | yes | captured |
| Callout figure | Annotated screenshot with numbered references | descriptive | captured + derivable |

## Editorial imagery

| Class | Purpose | Established | Origin |
|---|---|---|---|
| Spot illustration | Small thematic mark beside a text block | yes | drawn |
| Card image | Identifies one item in a collection or grid | yes (DocC `purpose: "card"`) | drawn |
| Thumbnail | Reduced stand-in for a larger item; not separately authored | yes | derivable |
| Hero image | Full-bleed, top of page, sets the register | yes | shot or drawn |
| Key art | Large, brand-forming, campaign-level | yes | drawn |
| Banner | Wide, short, promotional, usually carries text | yes | mixed |
| Open Graph image | Identity inside someone else's feed; fixed ratio, illegible at scroll size unless designed for it | yes | derivable |

## Ambient and treatment

| Class | Purpose | Established | Origin |
|---|---|---|---|
| Pattern / texture | Tiling surface, never focal | yes | derivable |
| Gradient field | Non-figurative background | yes | derivable |
| Scrim | Darkening gradient over an image, for legibility | yes | derivable |
| Ornament / divider art | Rhythm and separation | yes | derivable |

## State and motion

| Class | Purpose | Established | Origin |
|---|---|---|---|
| Empty state illustration | The absence of content, made intentional | yes | drawn |
| Error state illustration | Failure without blame | yes | drawn |
| Loading / skeleton | Structure before content | yes | derivable |
| Onboarding sequence | Ordered set that must read as one family | descriptive | drawn |
| Animated illustration | Motion-carrying asset (Lottie, SVG SMIL, video) | yes | drawn |
| Transition art | Continuity between two views | descriptive | derivable |

---

## Frequently confused pairs

**Icon vs. spot illustration.** Size does not separate them; role does. An icon
sits inside a control and is either actionable or labels something actionable.
A spot illustration is never interactive.

**Card image vs. key art.** A card image identifies one entry among many; key
art carries a campaign. There are many card images and at most one piece of key
art per view. Same visual language, different class, different rules.

**Hero image vs. key art.** Hero is a *placement*; key art is an *asset class*.
Key art can be placed as a hero, and a hero can be a photograph instead.

**Thumbnail vs. card image.** A thumbnail is derived; a card image is authored.
Systems that auto-shrink card images into thumbnails produce illegible
thumbnails, because the card image was composed for a size it is no longer
displayed at.

**Scrim is not an image.** It is a treatment applied to one. It belongs to the
tokens, not to the asset inventory.

---

## Construction vocabulary

Useful when decoding a reference, because the construction is measurable even
when the artwork is not reusable.

| Term | What it names |
|---|---|
| Papercut / paper-cut layering | One silhouette repeated at increasing offsets, each layer a step darker, soft drop shadows between layers |
| Offset path | The geometric operation that produces those layers |
| Topographic layering | The same effect read as contour lines |
| Interlace / knotwork | A continuous closed line in over-under crossing, no start and no end |
| Keyline shapes | The fixed primitives (circle, square, rectangle) an icon set is aligned to |
| Optical sizing | Adjusting a form so it *looks* the same weight at a different size |
| Optical alignment | Positioning by perceived centre rather than geometric centre |
| Appearance variant | The light/dark pairing, conventionally suffixed `~dark` |

---

## Consequences for a generating system

**Scope, per origin.** `derivable` classes can be delivered whole. `drawn`
classes can only be delivered as a system plus a seed set — promising a complete
icon library is a promise that cannot be kept. `captured` and `shot` classes get
rules, never assets.

**Provenance limit.** Construction rules are extractable from a reference —
layer count, offset amount, lightness step per layer, shadow radius, rotational
symmetry. The artwork is not. Layer geometry measured off a screenshot is
grade-C evidence and may not set a token on its own.

**Three classes missing from almost every design system**, though almost always
needed in practice: **empty state**, **error state**, and **Open Graph image**.
Worth making mandatory coverage.
