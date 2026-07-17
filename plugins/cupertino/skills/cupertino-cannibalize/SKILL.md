---
name: cupertino-cannibalize
description: >
  USER-INVOKED ONLY — never automatic per-PR, per-release, or part of
  cupertino-review's pipeline. Judges whether replacing a currently-
  successful product or feature is a deliberate, chosen cannibalization (the
  iPhone deliberately cannibalizing Apple's own iPod, "if we don't
  cannibalize ourselves, someone else will") versus a forced Vista Trap
  rewrite (see cupertino-longevity) — same surface symptom, opposite motive.
  Use ONLY when explicitly asked, on an ongoing post-ship cadence — "should
  we cannibalize our own product", "replace our most successful feature
  before a competitor does", "self-disruption check", or a direct request to
  evaluate obsoleting the team's own most successful thing. Do NOT trigger on
  routine PR/release review or any automatic pipeline step — it requires an
  explicit, standalone request.
---

Cannibalize yourself before someone else does — but only when it's a
genuine, deliberate choice, not a decaying architecture forcing your hand.
Full grounding (the iPhone-vs-iPod case, the exact distinguishing test) and
the reasoning for why this must never run automatically live in
`../../references/cannibalize.md` — read it in full before applying this
technique.

## When to use — user-invoked only, explicitly

This technique must **never** be triggered automatically — not on every PR,
not on every release, not as a standing item in `cupertino-review`'s
pipeline the way `cupertino-backwards` through `cupertino-reveal` run. Apply
it only when the user explicitly asks for this specific analysis. Deciding
to cannibalize your own most successful thing is a leadership-level call
with real, immediate costs; running this reflexively on every change would
manufacture constant unwarranted pressure to replace things that are
working fine and face no real competitive threat.

## The exact distinguishing test

"We're replacing this" can mean two opposite things:

- **Forced by decaying architecture = Vista Trap** (bad, avoid) — see
  `cupertino-longevity`. Tell: "could we have kept incrementally improving
  the old thing instead?" Honest answer: "no, the architecture won't allow
  it anymore."
- **Chosen because you can build the successor better than a competitor
  will = cannibalization** (good, deliberate) — this technique's subject.
  Tell: same question, honest answer: "yes, easily, we're choosing not to."

Same words, opposite motive, opposite response. Apply this test before
concluding which one a given "we're replacing this" actually is — see
`../../references/cannibalize.md` for the full statement and why getting
this right matters (the two call for opposite next steps).

## Process

1. **Name the current most-successful, most-load-bearing thing** the team
   would be most reluctant to touch.
2. **Apply the distinguishing test.** If the honest answer is "no, the
   architecture won't allow incremental improvement," stop — this is
   `cupertino-longevity`'s diagnostic, not this one; run that instead.
3. **If "yes, it could keep improving" — ask whether a competitor building
   the obvious successor is a real, credible threat**, not hypothetical.
   Manufacturing a fake threat to justify a rewrite misapplies this
   technique in the other direction.
4. **If the threat is real: decide explicitly** whether the team builds the
   successor itself. Name what's being deliberately made obsolete; accept
   the short-term cost as the price of not losing the long-term position.
5. **State the decision out loud** — chosen and owned, not discovered after
   the fact.

## Output

- The named current most-successful thing.
- The distinguishing-test verdict (Vista Trap vs. genuine cannibalization
  candidate), with the honest answer to "could this keep improving
  incrementally?" stated explicitly.
- If a genuine candidate: the competitive-threat assessment, and the
  explicit build-it-ourselves decision with what's being made obsolete.

## Relationship to other cupertino skills

Distinct from, and easily confused with, `cupertino-longevity` — both can
produce "we're replacing this," for opposite reasons. See
`../../references/cannibalize.md`'s "Why this is a distinct technique from
cupertino-longevity" section. Not part of `cupertino-review`'s automatic
pipeline — see that skill's own description of this step as
cadence-triggered and user-invoked only.
