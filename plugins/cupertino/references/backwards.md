# Start with the Customer Experience, Work Backwards

> "You've got to start with the customer experience and work backwards to the
> technology. You can't start with the technology and try to figure out where
> you're going to try to sell it."
> — Steve Jobs, internal Apple talk, 1997 (the "What's the point of the Mac?"
> talk, given shortly after his return to Apple)

## The source moment

In 1997, freshly returned to a nearly-bankrupt Apple, Jobs stood in front of
Apple's own engineers and told them the company had been doing product
development backwards: starting from a technology or an internal capability
and then hunting for a market to point it at. His prescription was to reverse
the arrow — start from what the customer is actually trying to accomplish,
and work backwards from there to which technology serves it. This talk
predates and directly foreshadows the 1997 product-line cut
(`focus.md`) and the iMac/iPod/iPhone-era products that followed — all of
which shipped from a stated customer experience outward, not from a
component spec inward.

## The caveat that keeps this from being self-contradictory

Jobs also, famously, said the opposite-sounding thing:

> "A lot of times, people don't know what they want until you show it to
> them."

These are not in conflict, and this technique must never be applied as if
they were. The resolution:

- **"Start with the customer experience"** means empathy for the **problem**
  the customer actually has — the job they are trying to get done, the
  friction they feel, the moment that goes wrong for them today.
- **"People don't know what they want"** means the customer's own proposed
  **solution** (their literal feature request, their sketch of the UI, their
  guess at the mechanism) is frequently wrong or shallow, even when their
  diagnosis of the problem is completely correct.

So: take the customer's stated *pain* as real and load-bearing. Take the
customer's stated *feature request* as one data point, not the destination.
The technique is empathy for the problem, never literal transcription of
feature requests. A team that skips straight to building exactly what was
asked for has not applied this technique — it has abdicated the "work
backwards to the technology" half entirely, which requires someone to
actually do the work of figuring out what serves the experience, rather than
taking dictation.

## Applying it in software work

This runs **first**, before any architecture or design work starts on a new
feature or project — the technique is explicitly a pre-architecture gate, not
a retrospective UX polish pass.

1. **State the customer experience in one sentence, with no technology
   nouns in it.** If the sentence contains a database, a framework, an API
   shape, or a UI widget name, it is not yet a customer-experience
   statement — it has already smuggled in a technology answer. Rewrite until
   it describes only what the person is trying to accomplish and what
   "good" feels like when they get there.
2. **Separate the stated request from the underlying problem.** Write both
   down, explicitly, side by side. If a stakeholder asked for "a button that
   exports to CSV," the underlying problem might be "I need to hand this
   data to someone in another tool I don't control" — and the eventual
   answer might not be CSV at all.
3. **Work backwards.** Only once the experience is stated cleanly, ask what
   technology serves it — and be willing for that answer to differ from
   the original request. This is the step most teams skip; skipping it is
   exactly the backwards-development pattern Jobs was diagnosing in 1997.
4. **Flag when you can't tell the difference.** If the "customer experience"
   statement and the literal feature request are identical, that's a signal
   to dig one level deeper before treating the request as settled — either
   the request already *is* the right answer (it happens), or nobody has
   actually separated problem from solution yet.

## What this technique is not

- Not a mandate to ignore what users explicitly ask for — their diagnosis of
  the problem is usually the most valuable input in the room.
- Not a license to override user requests with an architect's personal
  taste dressed up as "customer empathy" — the discipline only holds if the
  customer-experience sentence is actually traceable to real customer pain,
  not to what the builder finds technically interesting.
- Not a one-time step to check off — if the technology direction chosen in
  step 3 turns out not to serve the experience from step 1, that is a signal
  to revisit, not evidence the technique failed.

## Where this sits in the cupertino lifecycle

First technique in `cupertino-review`'s pipeline. Everything downstream —
`cupertino-focus`'s scoping, `cupertino-longevity`/`cupertino-integrate`'s
architecture calls, `cupertino-council`'s UI decisions — inherits whatever
customer-experience statement this step produced. A wrong or missing
statement here propagates as a wrong foundation for every later stage, which
is why this step runs first and is not optional inside the composed pipeline.
