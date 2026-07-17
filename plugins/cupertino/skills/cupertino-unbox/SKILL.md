---
name: cupertino-unbox
description: >
  Treats first-run, onboarding, and install — the first five minutes of
  contact — as designed theater, grounded in Apple's documented iPhone/iPad
  unboxing-as-theater packaging discipline ("the box is the first
  experience"). Use at build/finishing-time whenever a first-run flow,
  onboarding sequence, installer, or "getting started" experience needs
  attention — "improve our onboarding", "first-run experience", "the install
  feels rough", "getting started flow", "what do new users see first",
  "unboxing experience", "first five minutes". Distinct from cupertino-
  elevate, general-purpose transfiguration of any mid-life commodity feature
  — this is specifically and only the first-contact moment.
---

The box is the first experience. Full grounding (Apple's iPhone/iPad
packaging discipline) and the 5-step method live in
`../../references/unbox.md` — read it in full before applying this
technique.

## When to use

Runs at **build/finishing-time** — after the core feature work
(`cupertino-council`, `cupertino-prototype`, `cupertino-elevate`) has
produced something worth a new user's first five minutes, and before
`cupertino-reveal`'s ship-time single addition. Applying this technique to
an install/onboarding flow that isn't otherwise finished yet just polishes
a moving target — hold off until the underlying feature work has settled.

## Process

1. **Trace the actual first five minutes, as it exists today** — the real
   sequence a new user hits, in order, exactly as it currently happens
   (not the intended sequence). Note every screen, prompt, error
   possibility, wait, and default.
2. **Identify what's revealed first, and whether that's a choice.** Is it
   the thing the user actually came for, or is it setup friction (a config
   file, a login wall, an empty dashboard)? If friction comes first, that's
   the single highest-leverage fix.
3. **Find the theater, not just the function.** Every step has to function
   — but ask, for each: does this moment communicate the product's
   character, or is it purely mechanical? The goal isn't adding delay, it's
   making necessary steps communicate something.
4. **Remove anything not earning its place in the first five minutes.**
   Does every screen/prompt/required action need to happen *now*, or can
   it be deferred to when it's actually needed?
5. **Build it.** Ship the redesigned first-run sequence as a real, working
   flow — not a description of what it should feel like. Match the
   project's actual stack.

## Output

1. The current sequence — the real first-five-minutes walk, as it exists
   today.
2. What's revealed first, and whether it's value or friction.
3. The theater moments — which steps were purely mechanical and how they
   now communicate character.
4. What got removed or deferred.
5. The build — the actual redesigned first-run flow, shipped.

## Distinction from cupertino-elevate — kinship, not overlap

See `../../references/elevate.md`'s "Distinction from cupertino-unbox"
section for the full statement. In short: `cupertino-elevate` is
general-purpose, applied opportunistically to any mid-life commodity
feature; this technique is specifically the first-contact moment, at a
fixed lifecycle point. Don't reach for this technique on a mid-life
settings page just because it happens to also be dull — that's
`cupertino-elevate`'s territory.
