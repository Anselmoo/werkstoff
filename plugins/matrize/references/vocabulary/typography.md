# Typography — reference vocabulary

Companion to `visual-asset-taxonomy.md`. Working vocabulary for naming type
decisions in a design system.

**Kind legend:** `token` — a stored value; `derived` — computed; `rule` — a
constraint needing an anti-rule; `property` — observed, not stored.

---

## Contents

- [What you are choosing](#what-you-are-choosing)
- [Variable font axes](#variable-font-axes)
- [Metrics](#metrics)
- [The scale](#the-scale)
- [Setting](#setting)
- [Detail](#detail)
- [Editorial slots](#editorial-slots)
- [Loading](#loading)
- [Frequently confused pairs](#frequently-confused-pairs)
- [Decoding notes](#decoding-notes)

---

## What you are choosing

| Term | What it names | Kind |
|---|---|---|
| Typeface | The design (Plus Jakarta Sans) | property |
| Font | One instance of it as a file (Plus Jakarta Sans Semibold) | property |
| Family | All instances that belong together | token |
| Superfamily | A design spanning categories — a sans and a serif sharing skeletons | property |
| Font stack | The ordered fallback list | token |
| System stack | The OS-native families, requested by name or by `system-ui` | token |
| Register | The role a family plays: display, body, UI, mono, script | rule |

## Variable font axes

| Term | What it names | Kind |
|---|---|---|
| `wght` | Weight, continuous | token |
| `wdth` | Width | token |
| `opsz` | Optical size — the axis that makes a face behave correctly at 11px and 90px | token |
| `slnt` / `ital` | Slant versus true italic; different things | token |
| `GRAD` | Grade: weight change without width change, used for dark-mode compensation | token |
| Named instance | A pinned point on the axes, exposed under a name | derived |

## Metrics

| Term | What it names | Kind |
|---|---|---|
| Em box | The design's coordinate square | property |
| Baseline | The line letters sit on | property |
| x-height | Height of the lowercase; the true driver of perceived size, far more than point size | property |
| Cap height | Height of the capitals | property |
| Ascender / descender | Above and below the x-height and baseline | property |
| Half-leading | The space a font adds above and below its own line box; the reason a heading sits lower in its box than expected | property |
| Leading trim | Removing that space so boxes align to the glyphs (CSS `text-box-trim`, `text-box-edge`) | rule |
| Cap-height alignment | Aligning by cap height rather than by box — what "optically aligned" usually means in practice | rule |
| `size-adjust` / `ascent-override` | Matching a fallback font's metrics to the webfont so nothing shifts on load | rule |

## The scale

| Term | What it names | Kind |
|---|---|---|
| Type scale | The ordered set of permitted sizes | token |
| Ratio | The multiplier between steps (1.200 minor third, 1.250 major third, 1.333 perfect fourth) | token |
| Modular scale | A scale generated from a ratio rather than chosen | property |
| Fluid type | Size interpolating between viewport bounds (CSS `clamp()`) | derived |
| Text style | A named bundle of size, weight, line-height and tracking (Apple: Large Title, Title 1…; Material: Display / Headline / Title / Body / Label) | token |
| Step | One entry; named semantically, not by pixel value | token |

**Text styles, not sizes.** A system whose tokens are `font-size-18` forces every
consumer to re-decide line-height and tracking. A system whose tokens are
`body-large` does not. This is the same tier argument as role-before-value in
colour.

## Setting

| Term | What it names | Kind |
|---|---|---|
| Line-height / leading | Vertical distance between baselines; unitless values scale with size, fixed ones do not | token |
| Tracking / letter-spacing | Uniform spacing across a run; must go negative as size increases and positive for all-caps | token |
| Kerning | Pair-specific spacing supplied by the font, not something you set | property |
| Measure | Line length, best expressed in `ch`; roughly 45–75 characters for body text | token |
| Alignment | left / right / centre / justified | rule |
| Rag | The shape of an unjustified edge; a good rag is a design outcome, not an accident | property |
| River | A visual channel of whitespace through justified text | property |
| Widow / orphan | A lone final line at the top of a column; a lone first line at the bottom | rule |
| Hanging punctuation | Pushing quotes and hyphens outside the measure so the edge looks straight | rule |
| Hyphenation | Breaking words at line end; language-dependent and essential in German | rule |

## Detail

| Term | What it names | Kind |
|---|---|---|
| Lining vs. oldstyle numerals | Cap-height figures versus figures with ascenders and descenders | token |
| Tabular vs. proportional numerals | Fixed-width figures for columns versus natural widths for prose — a table of numbers that jitters is using proportional figures | rule |
| Small caps | True small capitals, as opposed to scaled-down capitals | property |
| All caps | Requires added tracking and loses word-shape legibility; reserve for short labels | rule |
| Ligature | Combined glyph pair; standard versus discretionary | property |
| OpenType feature | The switch that enables any of the above (`font-feature-settings`, `font-variant-*`) | rule |
| Italic vs. oblique | A redrawn cut versus a slanted one; synthesised italics are neither | rule |

## Editorial slots

| Term | What it names | Kind |
|---|---|---|
| Eyebrow / kicker | The small label above a headline | token (a text style) |
| Headline | The primary line | token |
| Deck / standfirst | The summary between headline and body | token |
| Lede | The opening sentences of the body | property |
| Pull quote | Extracted text set larger | token |
| Caption | Text bound to a figure | token |
| Label | Text inside or beside a control | token |

## Loading

| Term | What it names | Kind |
|---|---|---|
| FOUT | Flash of unstyled text: fallback shows, then swaps | property |
| FOIT | Flash of invisible text: nothing shows until the font loads | property |
| `font-display` | Which of those you get (`swap`, `optional`, `block`) | rule |
| Subsetting | Shipping only the glyphs actually used | rule |
| Preload | Fetching the critical font early | rule |

---

## Frequently confused pairs

**Typeface vs. font.** The design versus the file. Nobody will correct you in
conversation, but a lexicon that uses them interchangeably cannot express "one
typeface, four fonts, two variable axes".

**Leading vs. line-height.** Historically leading was the *added* metal between
lines; CSS line-height is the *total*. A 16px type with 24px line-height has 8px
of leading, not 24. Worth stating once in the lexicon so nobody halves the value.

**Kerning vs. tracking.** Kerning is per-pair and comes from the font. Tracking
is uniform and is yours. "Kern it looser" is a request nobody can fulfil.

**Weight vs. optical size.** Both make text look heavier. Only one of them is
about size. A display cut used at body size looks spindly, and the fix is the
`opsz` axis, not more weight.

**Point size vs. perceived size.** Two faces at 16px look different sizes if
their x-heights differ, which they do. This is why swapping a typeface always
requires re-tuning the scale, and why "we kept the same sizes" is not a neutral
change.

**Display cut vs. body cut.** Tighter spacing, finer hairlines, made for large
sizes. Using one for body text is the most common typographic error in
design systems built by engineers.

---

## Decoding notes

- **Families — grade A.** `@font-face` and `font-family` are declared.
- **Sizes — grade B** from declared CSS; the *scale* must then be inferred by
  looking for a consistent ratio between steps. Record both the observed sizes
  and the inferred ratio, separately.
- **Line-height — grade B**, and note whether it is unitless or fixed; that
  difference is a design decision, not a formatting detail.
- **Tracking — grade B**, and negative values at display sizes are the signal
  that the reference is tracking deliberately rather than defaulting.
- **Measure — grade B** via container width divided by an approximate character
  width; grade C from an image.
- **Optical size axis — grade A** if a variable font is served, otherwise absent.
- **Text-style bundles — inferable, not measurable.** You can see that all
  headings share a size, weight and line-height combination; you cannot see what
  the system calls it. Mark the inference.

Record ratios, not pixel values. "Headline is 2.25× body" survives a change of
base size; "36px" does not — and the ratio is the part the reference actually
decided.
