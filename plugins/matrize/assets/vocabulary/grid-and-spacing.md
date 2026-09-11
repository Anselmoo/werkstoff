# Grid and Spacing — reference vocabulary

Companion to `visual-asset-taxonomy.md`. Working vocabulary for naming the
spatial decisions in a design system.

**Kind legend** — where the term lives in the system:

| Kind | Meaning |
|---|---|
| `token` | A stored value. Belongs in `tokens.json`. |
| `derived` | Computed from tokens. Never stored separately. |
| `rule` | A constraint on use. Belongs in the lexicon with an anti-rule. |
| `property` | Something you observe or measure, not something you store. |

Vendor-specific terms are attributed inline.

---

## The scale itself

| Term | What it names | Kind |
|---|---|---|
| Base unit | The smallest increment everything else is a multiple of (4px and 8px are the common choices) | token |
| Spacing scale / ramp | The ordered set of permitted spacing values | token |
| Spacing step | One entry in that set, addressed by name rather than value | token |
| Linear scale | Steps as integer multiples of the base unit (4, 8, 12, 16, 20…) | property |
| Modular scale | Steps as a geometric progression (4, 8, 16, 32, 64…) | property |
| Hybrid scale | Linear in the small range, modular in the large — what most mature systems actually use | property |
| T-shirt naming | `xs`, `sm`, `md`, `lg`, `xl` instead of numbers; survives inserting a step, numeric naming does not | rule |
| Density | A global multiplier producing comfortable / compact variants of the same layout | token |

## Page and layout grid

| Term | What it names | Kind |
|---|---|---|
| Column grid | The repeating vertical division of the layout | token |
| Column | One division | token |
| Gutter | The space *between* columns | token |
| Margin | The space between the content area and the viewport or page edge | token |
| Field | Column plus one gutter, treated as the repeating unit | property |
| Container / content width | The maximum width the content area reaches | token |
| Subgrid | A nested grid inheriting the parent's tracks (CSS `subgrid`) | rule |
| Bleed / full-bleed | Content deliberately crossing the margin to the edge | rule |
| Safe area / inset | Region kept clear of device chrome (notches, home indicators) | derived |

## Vertical structure

| Term | What it names | Kind |
|---|---|---|
| Baseline grid | A regular horizontal rhythm that text baselines sit on | token |
| Vertical rhythm | The perceived regularity produced by a baseline grid | property |
| Leading trim | Removing a font's built-in half-leading so boxes align optically (CSS `text-box-trim`) | rule |
| Optical margin | Adjusting a value because the perceived edge differs from the geometric one | rule |

## Responsive behaviour

| Term | What it names | Kind |
|---|---|---|
| Breakpoint | A viewport width at which layout rules change | token |
| Media query | A condition on the viewport | rule |
| Container query | A condition on the *parent element's* size, not the viewport — the reason a component can be reused at any width without knowing where it is | rule |
| Adaptive | Discrete layouts that switch at breakpoints | property |
| Fluid | Continuous scaling between bounds (CSS `clamp()`) | property |
| Fluid space | Spacing that scales with viewport, not only type | derived |

## Box-level spacing

| Term | What it names | Kind |
|---|---|---|
| Padding | Space inside a box, between border and content | derived from token |
| Margin (box) | Space outside a box — the same word as page margin, different concept | derived from token |
| Gap | Space between grid or flex children (CSS `gap`); replaces margin-based spacing and cannot collapse | derived from token |
| Inline / block axis | Direction names that survive writing-mode changes; `inline-start` rather than `left` | rule |
| Stack | A vertical rhythm primitive: one spacing value applied between all siblings | rule |
| Inset | Uniform padding applied as a named step | derived |

## Depth

| Term | What it names | Kind |
|---|---|---|
| Elevation | The named level of a surface above the background | token |
| Z-index scale | Named stacking levels, so nobody writes `z-index: 9999` | token |
| Stacking context | The subtree within which z-index is meaningful — the reason a correct z-index sometimes has no effect | property |
| Shadow ramp | The set of shadows mapped one-to-one onto elevation levels | token |
| Surface tint | Lightening a surface with elevation instead of, or alongside, a shadow (Material) | token |

---

## Frequently confused pairs

**Gutter vs. gap.** Gutter is a property of the *grid definition*; gap is the CSS
property that realises it. They usually hold the same value and are not the same
thing — a design with a 24px gutter may use a 24px gap, but a nested flex row
also uses gap and has no gutter.

**Margin (page) vs. margin (box).** The single most common vocabulary collision
in design systems. If both appear in your lexicon, rename one. `page-inset` and
`space-outside` both work.

**Baseline grid vs. spacing scale.** A baseline grid governs *text* alignment; a
spacing scale governs *box* separation. They can be made to agree (a 4px base
unit and a 24px line-height agree), but they answer different questions and a
system can have one without the other.

**Breakpoint vs. container query.** A breakpoint asks how big the window is; a
container query asks how big the available slot is. Components that use
breakpoints break when reused in a sidebar. This is the single biggest change in
layout practice since the breakpoint era, and any system documenting only
breakpoints is documenting an older craft.

**Padding scale vs. spacing scale.** Frequently the same set, and that is a
choice, not a law. Component interiors often want a finer ramp than page
sections do.

---

## Decoding notes

What a reference actually yields, and at what reliability:

- **Base unit — inferable at grade B.** Collect all observed spacing values and
  take the greatest common divisor. If the GCD is 1, there is no grid, and that
  is itself the finding.
- **Spacing scale — grade B** from declared CSS, grade C from screenshots. Never
  set a step from a screenshot alone.
- **Column count and gutter — grade B.** Declared in the stylesheet on most
  sites; readable but imprecise from an image.
- **Container width — grade A or B.** Usually one declared `max-width`.
- **Baseline grid — grade C at best.** It lives in computed line boxes and is
  rarely declared as such. Record it as an open question rather than a number.
- **Density multiplier — usually not recoverable.** Most sites ship one density.
  Its absence in a reference is not evidence the system lacks one.

Record ratios, not absolutes. "Section spacing is 2× card padding" survives a
rescale; "48px" does not.
