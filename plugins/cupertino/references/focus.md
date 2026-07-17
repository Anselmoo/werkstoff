# Focus Is Saying No

> "Focus is about saying no. ... Innovation is saying no to 1,000 things."
> — Steve Jobs

## The source moment

When Jobs returned to Apple in 1997, the company had roughly a dozen
variations of the Macintosh alone, plus printers, scanners, digital cameras,
and the Newton — a product line so sprawling that Apple's own employees and
retail partners struggled to explain, in one sentence, which product a given
customer should actually buy. Jobs' well-documented response, delivered in
front of the whole company, was to draw a single 2x2 grid on a whiteboard:

|              | Consumer | Pro |
|--------------|----------|-----|
| **Desktop**  | iMac     | Power Mac |
| **Portable** | iBook    | PowerBook |

Roughly 40 confusing, overlapping products were cut down to four — one per
quadrant. This is the single most-cited example of Apple-style focus, and it
is a **portfolio/roadmap-altitude** decision: which products or feature
lines exist at all, not how any one of them looks or behaves.

## What focus actually costs

Focus is not primarily a creative act — it is a subtraction with real,
named losses:

- Products that had real, if small, revenue and real, if small, champions
  inside the company were killed.
- Teams were reorganized or let go.
- Customers who liked a niche variant lost it, with no direct replacement.

The 2x2 grid worked because Jobs was willing to accept those losses in
exchange for a company that could explain its whole product line in one
sentence, ship each surviving line at higher quality, and stop splitting
engineering attention four ways. Saying no is not free, and pretending it is
free is how "focus" work degrades into vague decluttering.

## Applying it in software work

This runs **early, at scoping time** — before deep design or architecture
work begins on the surviving portfolio, immediately after
`cupertino-backwards` has established what customer experience actually
matters.

1. **Enumerate the real portfolio.** List every product, feature line, mode,
   platform target, or persona-variant currently shipped or currently
   planned — not just the ones under active discussion. Sprawl usually
   includes things nobody has proposed cutting because nobody is looking at
   the whole list at once.
2. **Draw the equivalent of the 2x2 grid.** Find the two (or occasionally
   three) axes that actually matter for this product — not necessarily
   consumer/pro x desktop/portable, but some real structural split the
   business or the users care about. Place every item from step 1 into a
   cell.
3. **Name what gets cut, and name the cost out loud.** For each cell that
   is empty, ambiguous, or duplicated by another cell, decide explicitly:
   kill it, merge it into a surviving cell, or defend why it's actually a
   fifth legitimate cell (rare — usually a sign the axes are wrong, not that
   a fifth cell is warranted). State what is lost, not just what is gained.
4. **Check that the survivors can each be explained in one sentence.** If a
   surviving product/feature line still needs a paragraph of caveats to
   describe, the cut wasn't deep enough.

## Distinction from cupertino-council — do not conflate these

`cupertino-focus` and `cupertino-council` (specifically the Reduction lens's
principle inside the council) operate at **different altitudes**
and must not be treated as the same move:

- **`cupertino-focus`** operates at **roadmap/portfolio altitude**: which
  products, features, platforms, or user-facing modes exist at all. Its
  unit of analysis is a whole feature line or product variant. Running it
  answers "should this thing exist in our lineup."
- **`cupertino-council`** (the Reduction lens specifically) operates at
  **UI-element altitude**: which buttons, panels, options, or visual
  elements exist within one already-scoped interface. Its unit of analysis
  is a widget, a settings toggle, a menu item. Running it answers "should
  this element exist on this screen."

A council session cannot substitute for a focus session and vice versa: the
Reduction lens vetoing a settings toggle inside `cupertino-council` does not
tell you whether the feature that toggle belongs to should exist as a
product line at all, and running `cupertino-focus` on a whole portfolio does
not tell you whether any single surviving product's UI is well-designed.
Both are reduction, both draw on the same Jobs-grounded discipline, but they
are not interchangeable and `cupertino-review`'s pipeline runs them at different
lifecycle moments for exactly this reason.

## Where this sits in the cupertino lifecycle

Second technique in `cupertino-review`'s pipeline, run early at scoping time
— after `cupertino-backwards` establishes the customer experience, before
any architecture decisions (`cupertino-longevity` / `cupertino-integrate`)
commit engineering effort to a specific surviving portfolio shape.
