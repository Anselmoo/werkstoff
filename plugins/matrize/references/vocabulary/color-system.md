# Colour Systems — reference vocabulary

Companion to `visual-asset-taxonomy.md`. Working vocabulary for naming colour
decisions, with emphasis on the distinction most systems get wrong: **role
before value**.

**Kind legend:** `token` — a stored value; `derived` — computed; `rule` — a
constraint needing an anti-rule; `property` — observed, not stored.

---

## Contents

- [Token tiers](#token-tiers)
- [Colour spaces and gamut](#colour-spaces-and-gamut)
- [Ramps](#ramps)
- [Semantic roles](#semantic-roles)
- [Appearance and state](#appearance-and-state)
- [Contrast and accessibility](#contrast-and-accessibility)
- [Gradients](#gradients)
- [Frequently confused pairs](#frequently-confused-pairs)
- [Decoding notes](#decoding-notes)

---

## Token tiers

The single most consequential structure in a colour system. Skipping a tier is
what makes a system unable to support a second appearance mode later.

| Term | What it names | Kind |
|---|---|---|
| Primitive / global token | A raw value with no meaning: `red-500`, `neutral-200` | token |
| Alias / semantic token | A role pointing at a primitive: `color.action.dominant → red-500` | token |
| Component token | A role scoped to one component: `button.primary.background` | token |
| Role | What a colour *does*, independent of what it is | rule |
| Value | The colour itself | token |
| On-colour | The foreground guaranteed legible on a given surface (`on-primary`, Material) | token |

**The rule this tier structure encodes:** components reference roles, never
primitives. A component that names `red-500` cannot be re-themed and cannot
support dark mode without editing the component.

## Colour spaces and gamut

| Term | What it names | Kind |
|---|---|---|
| sRGB | The historical web gamut | property |
| Display P3 | The wider gamut most modern screens actually have | property |
| oklch / oklab | A perceptually uniform space; equal numeric steps look like equal steps, which sRGB HSL does not deliver | property |
| Gamut | The set of colours a space can express | property |
| Gamut mapping | What happens to an out-of-gamut colour on a narrower display; the reason a P3 accent can look flat on an older screen | rule |
| Perceptual uniformity | The property that makes a ramp generated in oklch look even without hand-correction | property |
| Relative colour syntax | Deriving one colour from another in CSS (`oklch(from var(--brand) l c h)`) | derived |
| `color-mix()` | Blending two colours in a named space | derived |

## Ramps

| Term | What it names | Kind |
|---|---|---|
| Ramp / scale | An ordered series of one hue from lightest to darkest | token |
| Step | One entry, named by number (50…950) rather than by appearance | token |
| Tint / shade | Lighter and darker derivations of a base | derived |
| Neutral ramp | The greyscale; usually the most-used and least-discussed part of a system | token |
| Warm / cool neutral | A neutral carrying a hue cast; a pure grey beside a warm brand reads as dirty | property |
| Anchor step | The one step in a ramp that equals the brand colour, from which the rest is generated | rule |

## Semantic roles

| Term | What it names | Kind |
|---|---|---|
| Brand | Identity; not necessarily usable as an action colour | rule |
| Action / interactive | The colour that means "this does something" | token |
| Status colours | success, warning, danger, info | token |
| Surface / background / elevated surface | The layers content sits on | token |
| Ink / foreground | Text and icon colour, usually in a strength ramp (primary, secondary, muted) | token |
| Border / hairline | Separation at low contrast | token |
| Accent | A colour used sparingly for emphasis, distinct from action | token |
| State layer | A translucent overlay expressing hover, focus, press (Material) | token |

## Appearance and state

| Term | What it names | Kind |
|---|---|---|
| Appearance / scheme | light, dark, and often high-contrast | rule |
| Forced colours mode | OS-level override (Windows High Contrast); a system must survive having its colours taken away | rule |
| Opacity | Transparency of an element | derived |
| Alpha | Transparency baked into a colour value | token |
| Tint | Mixing toward another colour without transparency — produces a predictable result over any background, unlike alpha | derived |
| Hover / press derivation | The rule by which an interactive colour darkens or lightens; a step in the ramp is more predictable than an opacity change | rule |

## Contrast and accessibility

| Term | What it names | Kind |
|---|---|---|
| Contrast ratio | WCAG 2 relative-luminance ratio, 1:1 to 21:1 | derived |
| AA / AAA thresholds | 4.5:1 body text, 3.0:1 large text and UI components, 7.0:1 AAA body | rule |
| Large text | 18.66px bold or 24px regular and above — a size threshold, not a judgement | rule |
| APCA / Lc | The perceptual contrast model drafted for WCAG 3; polarity-aware, where WCAG 2 is not | property |
| Non-colour redundancy | Every meaning carried by colour must also be carried by shape, position, or text | rule |
| Colour-blind safety | Checked against deuteranopia, protanopia, tritanopia — red/green status pairs are the usual failure | rule |

## Gradients

| Term | What it names | Kind |
|---|---|---|
| Colour stop | One position-and-colour pair | token |
| Interpolation space | The space the blend is computed in; sRGB blends through grey, oklch does not | rule |
| Linear / radial / conic | Gradient geometry | property |
| Mesh gradient | Multi-point blend, not expressible in plain CSS | property |
| Banding | Visible steps in a shallow gradient; mitigated by noise or a wider gamut | property |
| Duotone | Mapping an image's luminance onto two colours | derived |

---

## Frequently confused pairs

**Role vs. value.** `red-500` is a value; `action.dominant` is a role. A system
built on values cannot change its mind. This is the same defect that produced
`muted` and `quiet-action` pointing at one value under two names — two roles
sharing a value is legitimate, but it must be visible, and it only is if roles
exist as their own tier.

**Opacity vs. tint.** A 60% black overlay yields a different colour on every
background. A tinted token yields the same colour everywhere. Opacity is
convenient and unpredictable; prefer tint for anything that must meet a contrast
threshold.

**Saturation vs. chroma.** HSL saturation is not perceptual — equal saturation
at different lightnesses looks wildly unequal. Chroma in oklch is. Ramps
generated by varying HSL lightness alone are why so many hand-built palettes
have one muddy step in the middle.

**Contrast ratio vs. perceived contrast.** WCAG 2 is symmetric: it gives the
same number for dark-on-light and light-on-dark, though they do not look the
same. APCA is polarity-aware. Use WCAG 2 because it is the standard that will be
audited against, and know that it under-reports dark-mode problems.

**Dark mode is not inverted light mode.** Shadows stop working, saturated
colours vibrate, and pure black surfaces make elevation invisible. It is a
second set of role assignments, not a filter.

---

## Decoding notes

- **Values — grade A or B.** Declared hex or `oklch` in a stylesheet is reliable.
  Sampling from a screenshot is grade C and additionally wrong if the image has
  been through JPEG compression or a colour-managed pipeline, which it has.
- **Roles — not measurable, only inferable.** You can see that a colour appears
  on buttons; you cannot see whether the system calls it `action` or `brand`.
  Record the inference and mark it.
- **Ramps — grade B.** Usually fully declared as custom properties.
- **Contrast — always compute, never assert.** Compute it from the values you
  extracted, in code, and record which script did it. An asserted ratio is a
  claim; a computed one is a measurement.
- **Interpolation space — grade A** when declared, otherwise unknowable.

**Mandatory columns for any contrast table:** the pair, the ratio, the
thresholds it clears, **and the appearance mode**. A table that mixes
light-mode and dark-mode pairs without a mode column looks complete and is not —
it is the shape of the error that hides a role behaving differently in the two
modes.
