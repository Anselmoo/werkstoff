---
name: cupertino-focus
description: >
  Cuts a sprawling portfolio of products, features, platforms, or modes down
  to the smallest set each explainable in one sentence — grounded in Steve
  Jobs' 1997 return-to-Apple product-line cut, ~40 confusing products reduced
  to a 2x2 grid (consumer/pro x desktop/portable). Roadmap/portfolio-altitude
  reduction, distinct from cupertino-council's UI-element-altitude reduction.
  Use at scoping time, early in a project, when the portfolio is sprawling or
  unclear — "we have too many features", "which of these should we actually
  build", "focus is saying no", "cut the product line", "what should we NOT
  build", "our roadmap is a mess", "too many modes/variants", or any planning
  conversation where feature/product/platform count needs to shrink before
  design starts. Not for trimming UI elements on an already-scoped screen —
  that's cupertino-council's job.
---

Focus is saying no — deliberately, at portfolio altitude, and at real cost.
Full grounding (the 1997 talk, the 2x2 grid, what focus actually costs) and
the fixed, non-negotiable distinction from `cupertino-council`'s UI-altitude
reduction live in `../../references/focus.md`; read it in full before
applying this technique, especially the "Distinction from cupertino-council
— do not conflate these" section.

## When to use

Second technique in the `cupertino-review` lifecycle — runs early, at
scoping time, immediately after `cupertino-backwards` has established what
customer experience actually matters. Operates on a **portfolio**: which
products, feature lines, platforms, or user-facing modes exist at all. Not
for auditing which buttons or panels belong on one screen — that altitude
belongs to `cupertino-council` (see the altitude distinction in
`../../references/focus.md`, which must not be conflated with this
technique).

## Process

1. **Enumerate the real portfolio.** List every product, feature line,
   mode, platform target, or persona-variant currently shipped or planned —
   including the ones nobody has proposed cutting, since sprawl usually
   includes exactly those.
2. **Draw the equivalent of the 2x2 grid.** Find the two (rarely three)
   axes that actually matter for this product — not necessarily Apple's own
   consumer/pro x desktop/portable split, but a real structural split this
   business or these users care about. Place every item from step 1 into a
   cell.
3. **Name what gets cut, and say the cost out loud.** For every cell that's
   empty, ambiguous, or duplicated: kill it, merge it into a surviving
   cell, or explicitly defend a genuine fifth cell (rare — usually a sign
   the axes are wrong). State what's lost, not only what's gained.
4. **Check that every survivor fits in one sentence.** If a surviving
   product or feature line still needs a paragraph of caveats to describe,
   the cut wasn't deep enough — go back to step 3.

## Output

- The full enumerated portfolio (step 1).
- The grid with every item placed (step 2).
- A cut list: what's killed, what's merged, what survives, each with the
  cost stated explicitly (step 3).
- One sentence per surviving product/feature line (step 4) — if any
  survivor can't fit, flag it and return to step 3.

## Relationship to other cupertino skills

Runs after `cupertino-backwards`, before any architecture work
(`cupertino-longevity`/`cupertino-integrate`) commits engineering effort to
a specific surviving portfolio shape. Never conflate with `cupertino-
council` — see `../../references/focus.md` for the fixed altitude
distinction between the two; a focus session on a whole portfolio doesn't
tell you whether any surviving product's UI is well-designed, and a council
session on one screen doesn't tell you whether that screen's whole feature
should exist in the lineup.
