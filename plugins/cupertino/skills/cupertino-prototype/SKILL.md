---
name: cupertino-prototype
description: >
  Produces a minimal, cheap, real, actually-testable prototype to answer a
  specific load-bearing uncertainty by running it, not describing it —
  grounded in Apple's documented iPhone-era and iPod-scroll-wheel foam-
  core/aluminum prototyping process. The plugin's one generative/process
  technique; every other cupertino technique judges a finished thing, this
  one produces throwaway working versions early. Use at build-time, parallel
  to cupertino-council, when a debate turns on an empirical question rather
  than a values question — "will this actually be fast enough", "does this
  approach even work", "let's spike this first", "build a quick prototype",
  "proof of concept", "throwaway spike", "test this before we commit", or
  when an architecture debate (especially cupertino-longevity vs. cupertino-
  integrate) is stuck on a fact a cheap spike could settle. Not for judging a
  finished artifact — that's every other cupertino technique's job.
---

Judge by using the thing, not by describing it. Full grounding (the iPod
scroll-wheel prototyping process, why this is the plugin's one generative
technique, the 4-part core discipline) lives in
`../../references/prototype.md` — read it in full before applying this
technique.

## When to use

Runs at **build-time, parallel to `cupertino-council`** — while the council
establishes UI/frontend design principles, this technique produces the
runnable evidence that tests whether the underlying mechanism actually
works, independent of how it's styled. Also reach for this mid-architecture
debate: if `cupertino-longevity` and `cupertino-integrate` are arguing over
an empirical fact (which approach is actually faster, which handles the
real data shape, which has the failure mode someone's worried about) rather
than a values trade-off, stop debating and spike both approaches cheaply
instead.

## Process

1. **Name the specific question a prototype needs to answer** — the
   sharpest, cheapest-to-falsify version of the load-bearing uncertainty
   most likely to be wrong. Not "does this feature work" in general.
2. **Build the smallest runnable spike that answers that question.**
   Minimal, throwaway, not production code. Hardcode what isn't under test,
   skip irrelevant error handling, use the ugliest implementation that
   still produces a real, runnable answer. Architecting the spike for reuse
   is a sign it has quietly become a feature-development task wearing a
   prototype's name.
3. **Run it. Use it. Observe what breaks or surprises.** The evaluation is
   empirical — execute against real or realistic inputs, don't reason about
   what should happen.
4. **Extract the answer, then decide the spike's fate explicitly.** State
   what was learned in one or two sentences. Then explicitly decide: throw
   the spike away and build the real thing informed by it (the common
   case), or deliberately promote specific pieces — never by default, never
   silently.

## Output

- The specific question this prototype answers.
- What was built (cheap, real, runnable — not a mockup or description).
- What running it actually showed.
- The extracted answer, and the explicit decision on the spike's fate
  (discard vs. deliberately promote specific pieces).

## Relationship to other cupertino skills

Parallel to `cupertino-council` at build-time — the council governs how the
UI looks and behaves; this technique governs whether the mechanism
underneath actually works, proven by running it. Does not replace the
`cupertino-longevity`/`cupertino-integrate` tension-rule discussion — it
replaces guessing at facts a cheap spike could settle, not the values
trade-off between evolvability and tight ownership.
