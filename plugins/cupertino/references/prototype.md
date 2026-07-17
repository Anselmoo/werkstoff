# Relentless Cheap, Real Prototyping

> Apple's iPod scroll wheel and iPhone-era product decisions were not settled
> in slide decks. Teams cut foam-core mockups by hand, machined aluminum
> enclosures before the internals were finished, and built dozens of
> physically-holdable variants — judged not by describing them in a meeting
> but by picking them up, feeling the weight, spinning the wheel, and
> noticing what was wrong in a way no spec review would have caught.

This is well documented across Apple's industrial-design process: the iPod's
scroll wheel went through a large number of physical prototypes, evaluated
by hand-feel and one-thumb usability, before the mechanism and diameter were
settled. The point was never the elegance of any single prototype — it was
the speed and cheapness of the iteration loop, and the discipline of judging
by using the thing rather than debating a description of the thing.

## The one generative technique in this plugin

Every other technique in `cupertino` judges a finished-or-near-finished
thing: `cupertino-council` audits a design before/while it's built,
`cupertino-longevity`/`cupertino-integrate` judge an architecture decision,
`cupertino-elevate` transfigures a feature that already exists,
`cupertino-unbox` audits a first-run experience that already exists,
`cupertino-reveal` adds one thing to something already nearly shipped,
`cupertino-cannibalize` judges a replacement decision. `cupertino-prototype`
is the exception: it is about **producing** throwaway working versions
early, before there is a finished thing to judge. Every other technique in
this plugin implicitly assumes something concrete already exists to react
to — this technique is what makes that true in the first place, early
enough that the other techniques' judgments land on something real.

## The core discipline

1. **Cheap.** A prototype's cost should be proportional to how much you
   expect to throw it away — which, early on, is "almost entirely." Foam
   core, not machined aluminum; a script, not a service. If a prototype
   takes longer to build than the question it's meant to answer is worth,
   the prototype is too expensive.
2. **Real.** Not a mockup, not a slide, not a description — something that
   can actually be held, run, clicked, or executed. A rendering of a scroll
   wheel tells you nothing about how it feels under a thumb; a foam block
   the right diameter tells you everything a rendering can't. In software:
   a static screenshot of a flow tells you nothing about its actual
   latency, error states, or the way real data breaks your assumptions — a
   runnable spike does.
3. **Physically/actually testable.** The whole point is that someone
   interacts with the artifact directly, not with a description of it. If
   the only way to evaluate the prototype is to read about it or watch a
   recording, it hasn't cleared this bar yet.
4. **Judged by using, not by describing.** The verdict on a prototype comes
   from actually running it and observing what happens — not from a design
   review that reasons about it in the abstract. If the team's only
   evidence for "this will work" is a discussion, the prototype step hasn't
   actually happened yet, no matter how much whiteboarding occurred.

## Applying it in software work

This runs **at build-time, parallel to `cupertino-council`** — while the
council is establishing UI/frontend design principles, this technique is
producing the runnable evidence that tests whether the underlying mechanism
actually works, independent of how it's styled.

1. **Name the specific question a prototype needs to answer.** Not "does
   this feature work" in general, but the sharpest, cheapest-to-falsify
   version of the uncertainty — the load-bearing assumption most likely to
   be wrong. ("Can we actually stream this at the latency we're assuming?"
   "Does this data shape actually support the query pattern we need?")
2. **Build the smallest runnable spike that answers that question.**
   Minimal, throwaway, not production code — hardcode what isn't under
   test, skip error handling that isn't relevant to the question, use the
   ugliest implementation that still produces a real, runnable answer.
   Explicitly not architected for reuse; architecting a spike for reuse is
   a sign the spike has quietly turned into a feature-development task
   wearing a prototype's name.
3. **Run it. Use it. Observe what breaks or surprises.** The evaluation is
   empirical: execute the spike against real or realistic inputs and watch
   what actually happens, rather than reasoning about what should happen.
4. **Extract the answer, then decide the spike's fate explicitly.** State
   what was learned in one or two sentences. Then decide: throw the spike
   away and build the real thing informed by what was learned (the common
   case — the point was the question, not the code), or, rarely, promote
   specific pieces of it deliberately (never by default, and never
   silently — "we kept the spike's code" should be a stated decision, not
   an accident of nobody deleting it).

## Where this sits relative to "build minimal, runnable spike before
architecture debates"

The software-native framing of this technique: **build a minimal, runnable
spike before debating architecture in the abstract.** If `cupertino-
longevity` and `cupertino-integrate` are about to spend real time debating
which of two architectural approaches to a seam is right, and the debate is
turning on an empirical question (which approach is actually faster, which
actually handles the real data shape, which actually has the failure mode
someone is worried about) rather than a values question (evolvability vs.
tight ownership), that is the signal to stop debating and spike both
approaches cheaply instead. Prototyping does not replace the tension-rule
discussion in `longevity.md`/`integrate.md` — it replaces guessing at facts
that a cheap spike could just settle.

## Where this sits in the cupertino lifecycle

Runs at build-time, parallel to `cupertino-council` (per `cupertino-review`'s
pipeline) — both consume the architecture decisions already made by
`cupertino-longevity`/`cupertino-integrate` and both feed the same
build-time moment from different angles: the council governs how it looks
and behaves; this technique governs whether the mechanism underneath
actually works, proven by running it.
