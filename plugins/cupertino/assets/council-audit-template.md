# Council Audit Template

Fill this in during Steps 2–4. It is the structured "form" the council produces
before any code is written. Copy it, replace every bracket, delete nothing —
empty rows mean the audit wasn't run.

---

## Brief

- **Building**: [component / page / system — one line]
- **For whom**: [primary user and the moment they touch this]
- **Stack**: [HTML / React / Vue / etc. + constraints]
- **Emotional register**: [what should the user FEEL — one word, then a sentence]
- **Assumptions made** (if brief was thin): [list, or "none"]

---

## Step 2 — Council Brief

| Lens | Core question | Audit finding (one sentence, specific) |
|---|---|---|
| **Reduction** | What would you remove? | [the irreducible core IS ___; ___ has no defensible place] |
| **Craft** | Where is craft invisible? | [the invisible-craft opportunity is ___] |
| **Hierarchy** | Does depth create legibility? | [hierarchy holds/breaks at ___ because ___] |
| **Usability** | Where will the user be surprised? | [user is surprised at ___ when ___ goes silent] |
| **Metaphor** | Does it feel made by a human? | [the metaphor is ___; the warmth touchpoint is ___] |

---

## Step 3 — Tension Log

> Resolution hierarchy: Usability › Reduction › Craft › System coherence › Warmth
> (See references/resolution.md for the case library.)

1. **[Lens A] vs [Lens B]**: [A] wanted ___, [B] required ___ — resolved as ___
   because ___.
2. [additional tensions…]

*(If zero tensions: the audit was too shallow. Push harder before proceeding.)*

---

## Step 4 — Design Identity

**Lens contributions to the final design:**
- **Reduction**: [what reduction shaped the output]
- **Craft**: [what craft detail was committed to]
- **Hierarchy**: [what system structure was chosen]
- **Usability**: [what feedback model was adopted]
- **Metaphor**: [what warmth/metaphor was placed]

**Identity sentence** (specific enough to drive a visual decision):

> [one sentence — not "clean and modern"; something a developer could design from]

**Chosen system** (pulled from references):
- **Register**: [Surgical / Warm Editorial / Botanical / Twilight / Brutalist / Luxury / Playful]
- **Palette**: [name from palettes.md, dark or light]
- **Display font**: [from typography.md]
- **Body font**: [from typography.md]
- **Type scale ratio**: [1.25 default / 1.333 for drama]

---

## Step 5 — Build checklist (verify before shipping)

- [ ] Every visible element traces to a lens's decision (Reduction: nothing extraneous)
- [ ] Light source consistent across all shadows/elevations (Craft)
- [ ] Hierarchy survives dark mode AND mobile AND scaled content (Hierarchy)
- [ ] Every state handled: default, loading, empty, error, success (Usability)
- [ ] No silent state changes — every action has a perceptible consequence (Usability)
- [ ] Body text passes WCAG AA contrast (Usability)
- [ ] At least one genuine warmth touchpoint exists (Metaphor)
- [ ] All labels use the user's vocabulary, not the system's (Metaphor)
- [ ] Two font families maximum, both non-generic (Reduction + Metaphor)
- [ ] All color/spacing/type via CSS variables, none hardcoded (Hierarchy)
