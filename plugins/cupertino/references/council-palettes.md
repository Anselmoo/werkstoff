# Color Systems

Curated palettes for the build step. Each is a complete system: one **dominant**,
one **sharp accent**, and a neutral ramp — satisfying Craft (cohesion), Hierarchy (token
structure), and Reduction (commitment over hedging).

**How to use this**: Hierarchy sets the *register* (the emotional tone of the system).
Pick the register that matches the design identity sentence, then take the palette
as a starting point — adjust, don't copy blindly. Every value here is a CSS
variable candidate. Never hardcode.

Each palette lists `--bg`, `--surface`, `--text`, `--text-muted`, `--accent`,
`--accent-soft`, `--border`. That is a complete, Hierarchy-compliant token set.

---

## Register: Surgical (enterprise, precise, serious)

The interface is an instrument. Warmth comes from precision, not color. Near-
monochrome with a single decisive accent.

**Surgical Dark**
```
--bg:          #0B0D10
--surface:     #14171C
--text:        #E8EAED
--text-muted:  #8B919A
--accent:      #3D8BFF   /* one decisive blue */
--accent-soft: #1B2D4A
--border:      #23272E
```

**Surgical Light**
```
--bg:          #FAFAFA
--surface:     #FFFFFF
--text:        #1A1C1F
--text-muted:  #6B7178
--accent:      #0066FF
--accent-soft: #E6F0FF
--border:      #E4E6E9
```

---

## Register: Warm Editorial (magazine, considered, human)

Metaphor's register. Cream and ink rather than grey and black. Reads like print.

**Warm Editorial Light**
```
--bg:          #F4F1EA   /* paper cream */
--surface:     #FBF9F4
--text:        #1F1B16   /* warm near-black ink */
--text-muted:  #6E665A
--accent:      #C2410C   /* terracotta */
--accent-soft: #F3E2D6
--border:      #E0D9CC
```

**Warm Editorial Dark**
```
--bg:          #161310
--surface:     #211D18
--text:        #EDE6DA
--text-muted:  #9C9183
--accent:      #E8A04C   /* amber */
--accent-soft: #3A2E1E
--border:      #2E2820
```

---

## Register: Botanical (organic, calm, natural)

Green-anchored, low-saturation, restful. For tools meant to feel unhurried.

**Botanical Light**
```
--bg:          #F6F7F4
--surface:     #FFFFFF
--text:        #1C2420
--text-muted:  #5E6B62
--accent:      #2F7A4F   /* deep moss */
--accent-soft: #DDEEE3
--border:      #DDE3DC
```

**Botanical Dark**
```
--bg:          #0E1411
--surface:     #16201A
--text:        #E4EBE5
--text-muted:  #859189
--accent:      #4FB37A
--accent-soft: #1A2E22
--border:      #233029
```

---

## Register: Twilight (refined, premium, atmospheric)

Deep, saturated, jewel-toned. Premium consumer feel. Dominant dark with a glowing
accent — the closest to a "premium product page" register.

**Twilight Dark** (lead with this; light variant is secondary)
```
--bg:          #0A0A12
--surface:     #14141F
--text:        #ECEAF5
--text-muted:  #8884A0
--accent:      #A78BFA   /* used sparingly — see warning below */
--accent-soft: #241F3A
--border:      #22202E
```

> **Metaphor/Craft warning**: violet on near-black is one keystroke away from the
> generic "AI gradient" anti-pattern. It works *only* if the accent is used
> sparingly (single CTA, single highlight) and never as a full-bleed gradient
> on a white card. If in doubt, swap the accent to `#5EEAD4` (teal) or
> `#FB7185` (rose) to escape the cliché entirely.

---

## Register: High-Contrast Mono (brutalist, raw, confident)

Black, white, one alarm color. No grey hedging. For interfaces that want to feel
unapologetic.

```
--bg:          #FFFFFF
--surface:     #FFFFFF
--text:        #000000
--text-muted:  #555555
--accent:      #FF3B00   /* single alarm orange */
--accent-soft: #FFE8E0
--border:      #000000   /* borders are real, 1.5px+ */
```

---

## Rules that survive any register

1. **One dominant, one accent.** A third accent is Reduction's veto unless Hierarchy flagged
   a multi-state system (success/warning/error) — and even then, derive them.
2. **Accent appears rarely.** If everything is accented, nothing is. The accent
   marks the single most important action on screen.
3. **Neutrals are not pure grey.** Tint neutrals toward the dominant hue (warm
   greys in warm registers, cool greys in cool ones). Pure `#808080` is lifeless
   — an Craft failure.
4. **Borders earn their place.** In soft registers, prefer a surface elevation
   (a slightly lighter `--surface`) over a hard `--border`. In brutalist
   registers, borders are the whole point.
5. **Contrast is non-negotiable.** Body text must hit WCAG AA (4.5:1) against its
   background. This is a Usability requirement, not a suggestion — illegible text is a
   silent usability failure.
