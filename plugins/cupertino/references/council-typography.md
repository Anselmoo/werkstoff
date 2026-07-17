# Typography Systems

Display + body pairings for the build step. Every pairing avoids the banned
generics (Inter, Roboto, Arial, Helvetica, system-ui) and is traceable to a
design identity. Metaphor's principle: type carries warmth; Craft's principle: the
pairing must feel inevitable, not arbitrary.

**How to use this**: match the pairing to the design identity sentence from
Step 4. All fonts listed are available on Google Fonts unless noted, so they
load with a single `<link>` or `@import`. Pick *one* display and *one* body —
never more than two families (Reduction: a third typeface is clutter).

---

## Pairing by register

### Surgical (enterprise, precise)
- **Display**: `Space Grotesk` *(use cautiously — common; see warning)* or `Archivo`
- **Body**: `IBM Plex Sans` or `Public Sans`
- **Why**: geometric clarity, neutral but not characterless. Plex has subtle
  humanist details that keep it from feeling cold.

> **Warning**: `Space Grotesk` is the single most over-used "designer" font in
> AI output. If the identity is surgical, prefer `Archivo` or `Söhne` (commercial)
> to escape the convergence trap. The frontend-design skill explicitly flags
> Space Grotesk as an over-converged choice.

### Warm Editorial (magazine, human)
- **Display**: `Fraunces` (variable, with optical sizing — gorgeous at large sizes)
  or `Bricolage Grotesque`
- **Body**: `Newsreader` or `Source Serif 4`
- **Why**: Fraunces has wonky, characterful terminals that read as hand-considered
  — pure Metaphor warmth. Pair with a readable serif body for an editorial feel.

### Geometric Modern (clean, confident, product)
- **Display**: `Clash Display` (Fontshare, free) or `Cabinet Grotesk` (Fontshare)
- **Body**: `Satoshi` (Fontshare) or `Hanken Grotesk`
- **Why**: Fontshare families are distinctive, free, and almost never appear in
  generic output — instant differentiation from the Inter crowd.

### Botanical / Calm (organic, unhurried)
- **Display**: `Instrument Serif` (high contrast, elegant) or `Gloock`
- **Body**: `Hanken Grotesk` or `Mulish`
- **Why**: a high-contrast display serif against a soft humanist sans creates
  calm, breathing hierarchy.

### Brutalist / Raw (unapologetic)
- **Display**: `Anton` or `Archivo Black` or a monospace at display size (`Departure Mono`)
- **Body**: `Inconsolata` or `JetBrains Mono` (yes — mono body is a statement)
- **Why**: brutalism wants weight and rawness. Monospace as body text is a
  deliberate, confident choice that signals "this is a tool, not a brochure."

### Luxury / Refined (premium, restrained)
- **Display**: `Cormorant Garamond` (very high contrast, expensive feel) or `Ogg` (commercial)
- **Body**: `EB Garamond` or `Spectral`
- **Why**: high-contrast old-style serifs read as luxury. Generous leading and
  letter-spacing on the display does the rest.

### Playful / Toy-like (friendly, approachable)
- **Display**: `Fredoka` or `Baloo 2` (rounded, friendly)
- **Body**: `Nunito` or `Quicksand`
- **Why**: rounded terminals signal friendliness. Use Metaphor's warmth here freely —
  this register invites it.

---

## Type scale (Hierarchy's hierarchy, made concrete)

Three visible levels. Use a consistent ratio. A 1.25 (major third) scale is a
safe, versatile default:

```
--text-xs:   0.8rem    /* metadata, captions — tertiary */
--text-sm:   0.9rem    /* secondary body */
--text-base: 1rem      /* primary body */
--text-lg:   1.25rem   /* subheadings */
--text-xl:   1.563rem  /* section headings — secondary hierarchy */
--text-2xl:  1.953rem  /* page headings — primary hierarchy */
--text-3xl:  2.441rem  /* hero — use once per page maximum */
--text-4xl:  3.052rem  /* display moments — rare */
```

For editorial/luxury registers, push the display sizes higher (4–6rem) and the
ratio steeper (1.333 perfect fourth) — drama lives in the jump between sizes.

---

## Rules that survive any pairing

1. **Two families maximum.** One display, one body. A third is Reduction's veto.
2. **Pair contrast, not similarity.** A characterful display against a quiet body
   reads better than two similar fonts. Two grotesques together is muddy.
3. **Leading is a design decision.** Body line-height 1.5–1.7; headings 1.1–1.25.
   Tight leading on body text is an Craft failure (cramped); loose leading on
   headings is too (disconnected).
4. **Letter-spacing display type negative, body type zero.** Large type tightens
   (`letter-spacing: -0.02em`); body stays at 0; all-caps labels open up
   (`+0.05em`).
5. **Variable fonts where possible.** `Fraunces`, `Bricolage Grotesque`, and
   `Hanken Grotesk` are variable — one file, full weight range, less network cost.
   This is Hierarchy's system-efficiency principle applied to type.
6. **Never converge.** Across separate builds, vary the pairing. Reaching for the
   same font every time (the Space Grotesk reflex) is the convergence trap the
   council exists to break.
