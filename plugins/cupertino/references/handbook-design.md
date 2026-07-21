# Handbook dimensions — Design

Apple-engineering-craft framing: clarity, restraint, consistency —
informed by, not copied from, the HIG and Primer's design-systems
methodology. `cupertino` already has rich, curated design material from
`cupertino-council`; this file is mostly a **pointer document** into that
material rather than a second copy of it. `cupertino-handbook-draft` reads
this table to know, per dimension, whether to point at existing council
material or analyze/scaffold something new.

| Dimension id | Title | Source of truth | New content needed here |
|---|---|---|---|
| `color-palette` | Color & palette | `council-palettes.md` | none — pointer only |
| `typography` | Typography | `council-typography.md` | none — pointer only |
| `tokens` | Spacing / motion / elevation tokens | `tokens-starter.css` | none — pointer only |
| `component-states` | Component inventory & states | — | **new** |
| `layout-grid` | Layout / grid & responsive breakpoints | — | **new** |
| `iconography` | Iconography & imagery register | — | **new** |
| `accessibility-baseline` | Accessibility baseline | `tokens-starter.css` + Usability lens | **new** (rule text, detection signals) |
| `voice-microcopy` | Voice & microcopy | Metaphor lens (`council-lenses.md`) | **new** |

## `component-states` — Component inventory & states

**Rationale**: Ties to the Usability lens's null-state discipline
(`council-lenses.md`): "every state must be handled, none silently."

**What the draft step analyzes/scaffolds**: catalog the components in use
(or, for an empty project, the components the scoped feature set implies)
and, for each, whether its default/hover/disabled/loading/error/empty
states are explicitly defined anywhere (CSS, component code, or design
notes).

**Detection signal**: a new interactive component shipped with only a
default state defined — no visible handling for disabled, loading, or
error.

## `layout-grid` — Layout / grid & responsive breakpoints

**Rationale**: Ties to the Hierarchy lens's "contextual continuity" — does
a layout hold up across breakpoints, not just the one it was built at.

**What the draft step analyzes/scaffolds**: the base grid unit in use,
named breakpoints (or their absence), and whether the project has settled
on container queries vs. media queries.

**Detection signal**: a new layout using a raw pixel breakpoint not
matching any named breakpoint in the handbook, or a fixed-width container
with no responsive behavior at all.

## `iconography` — Iconography & imagery register

**Rationale**: Ties to the Metaphor lens — "every icon or label should
invoke a real-world object or action the user already understands."

**What the draft step analyzes/scaffolds**: the icon set/library already
in use (or chosen for an empty project) and the illustration/imagery
register (see `council-palettes.md`'s named registers) it should stay
consistent with.

**Detection signal**: a new icon introduced from a different icon set/style
than the one already established, or raw emoji used as interface iconography
where the handbook's register calls for a consistent icon set.

## `accessibility-baseline` — Accessibility baseline

**Rationale**: Usability's veto (`council-palettes.md` "Rules that survive
any register" #5: "Contrast is non-negotiable. Body text must hit WCAG AA
(4.5:1) against its background."); `tokens-starter.css`'s
`prefers-reduced-motion` media query.

**Rule** (verbatim, ready to drop into the artifact template): Body text
must hit WCAG AA (4.5:1) against its background; every interactive element
has a visible `:focus-visible` ring; `prefers-reduced-motion` is honored.

**Detection signal**: new CSS/component code introducing a color pair
failing 4.5:1, or a `:focus` override with no `:focus-visible` fallback, or
an animation with no `prefers-reduced-motion` guard.

## `voice-microcopy` — Voice & microcopy

**Rationale**: Metaphor's empty-state test (`council-lenses.md`): "If it
says 'No items found' it fails Metaphor. If it says something a thoughtful
person would say, it passes." Also draws on "Labels from the user's
vocabulary: 'Save changes' not 'Submit'."

**What the draft step analyzes/scaffolds**: the tone rules already implied
by existing labels/error messages/empty states (or, for an empty project,
a stated tone commitment — e.g. "plain, direct, no jargon") for labels,
empty states, and error messages specifically.

**Detection signal**: a new user-facing string that is a raw system/database
term ("null", "undefined", "Error: entity not found") rather than
user-vocabulary language, or a generic empty-state string ("No items
found", "No data").
