# Icon Systems — reference vocabulary

Companion to `visual-asset-taxonomy.md`. Working vocabulary for the construction
and governance of an icon set.

**Kind legend:** `token` — a stored value; `derived` — computed; `rule` — a
constraint needing an anti-rule; `property` — observed, not stored.

---

## Contents

- [Construction geometry](#construction-geometry)
- [Stroke and form](#stroke-and-form)
- [Size and scaling](#size-and-scaling)
- [Style and variants](#style-and-variants)
- [Meaning and governance](#meaning-and-governance)
- [Delivery](#delivery)
- [Frequently confused pairs](#frequently-confused-pairs)
- [Decoding notes](#decoding-notes)

---

## Construction geometry

| Term | What it names | Kind |
|---|---|---|
| Canvas / artboard | The nominal square an icon is drawn in (24×24 is the common default) | token |
| Live area | The inner region the artwork may occupy | token |
| Trim area | The absolute maximum, used only by deliberately oversized forms | token |
| Padding / clearance | Canvas minus live area; what keeps icons from touching their neighbours | derived |
| Keyline shapes | The fixed primitives every icon aligns to — circle, square, portrait rectangle, landscape rectangle, and often two diagonals | token |
| Optical volume | The principle that keylines exist to make shapes look equally large, not be equally large — a circle must exceed a square to match it | rule |
| Grid fitting | Aligning strokes to the pixel or half-pixel grid so they render crisply | rule |

## Stroke and form

| Term | What it names | Kind |
|---|---|---|
| Stroke weight | Line thickness, constant across the set | token |
| Terminal | How a stroke ends: butt, round, or square | token |
| Join | How two strokes meet: miter, round, bevel | token |
| Corner radius | The radius applied at direction changes in the artwork | token |
| Counter | Enclosed negative space; must survive reduction | rule |
| Stem / apex / terminal | Borrowed from type; useful when an icon set must sit beside a specific typeface | property |

## Size and scaling

| Term | What it names | Kind |
|---|---|---|
| Size ramp | The permitted rendered sizes (16 / 20 / 24 / 32 is typical) | token |
| Optical size | A separately drawn master for a given size — not a scaled version | token |
| Optical sizing | Adjusting form so weight *looks* constant across sizes; a 24px icon scaled to 16px looks heavier than a drawn 16px icon | rule |
| Pixel snapping / hinting | Nudging geometry onto whole pixels at small sizes | rule |
| Micro icon | The smallest tier, usually a simplified drawing rather than the same one | property |

## Style and variants

| Term | What it names | Kind |
|---|---|---|
| Outlined / line | Stroke-only | property |
| Filled / solid | Filled shape, typically used for selected state | property |
| Duotone / two-tone | Two opacities or two hues of one colour | property |
| Style pair | Outlined and filled versions of the same metaphor, used as a state pair | rule |
| Weight axis | A variable-font axis varying stroke weight continuously (SF Symbols, Material Symbols) | token |
| Appearance variant | Light and dark renderings, conventionally suffixed `~dark` | derived |

## Meaning and governance

| Term | What it names | Kind |
|---|---|---|
| Metaphor | The real-world referent the icon depends on; culturally and generationally bound (the floppy disk) | rule |
| Affordance | What the icon suggests can be done | property |
| Semantic vs literal naming | `delete` versus `trash-can` — semantic names survive a redraw, literal names do not | rule |
| Icon family | The set as a whole; coherence is a property of the family, not of any member | property |
| Growth rule | The stated procedure by which a new icon is added, so the set stays coherent without its author | rule |
| Directionality | Whether an icon mirrors under right-to-left layout — arrows do, clocks do not | rule |
| Composed icon | Base icon plus badge or overlay, assembled rather than drawn | derived |

## Delivery

| Term | What it names | Kind |
|---|---|---|
| Inline SVG | Markup in the document; styleable, no extra request, inflates the DOM | property |
| SVG sprite | One file, referenced by `<use>`; cacheable | property |
| Icon font | Glyphs in a font file; legacy, breaks with font blocking, poor accessibility | property |
| `currentColor` | The SVG fill that inherits text colour — the reason an icon needs no colour token of its own | rule |
| Accessible name | The label a screen reader announces; decorative icons take `aria-hidden` instead | rule |

---

## Frequently confused pairs

**Stroke weight vs. optical weight.** Stroke weight is a number; optical weight
is how heavy the icon *looks*, which depends on how much of the canvas the form
covers. Two icons at identical stroke weight can look unequal, and correcting
that is drawing, not configuration.

**Keyline shapes vs. the grid.** The grid is the coordinate system; keylines are
the permitted silhouettes within it. An icon can be perfectly on-grid and still
off-keyline, which is what makes a set look almost-right.

**Filled vs. duotone.** Filled is one colour; duotone is two values of one
colour. They read as different families and should not be mixed within a set.

**Icon font vs. SVG.** Not a style choice. Icon fonts fail when font loading
fails, are announced as garbage characters by some screen readers, and cannot
carry two colours. Treat this as settled rather than open.

**Scaling vs. optical sizing.** Scaling is free and wrong at the extremes;
optical sizing costs a drawing per size. Most sets need it only at 16px and
below.

---

## Decoding notes

- **Stroke weight — grade B.** Readable from an SVG's `stroke-width`, estimable
  from a screenshot at grade C.
- **Canvas and live area — grade A** when the SVG `viewBox` is available; not
  otherwise recoverable.
- **Keyline shapes — grade C, and rarely worth the attempt.** Published sets
  document them (Material does); unpublished sets require reverse-engineering
  from a dozen members, and the result is a hypothesis.
- **Size ramp — grade B** from declared CSS.
- **Corner radius and terminals — grade A** from the SVG path, grade C from an
  image.
- **Growth rule — never recoverable.** It is a decision, not a measurement, and
  must be authored.

The honest output for a project with no drawn set is a **placeholder strategy**:
adopt an existing open set, record which one and at what stroke weight and size
ramp, and state the conditions under which a brand-owned set would replace it.
That is a first-class result, not an admission of failure — the reference
sketchbook gets this exactly right by naming Lucide, its stroke weight, and its
terminal style, and saying what would supersede it.
