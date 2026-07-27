---
name: cupertino-unbox
description: "Use at build/finishing-time, after core feature work has produced something worth a new user's first five minutes, to redesign the actual first-run, onboarding, or install flow. Trigger on 'improve onboarding', 'first-run experience', 'unboxing', 'install flow', 'first five minutes'. Scope is strictly the first five minutes of first contact — not the whole onboarding arc, and not to be confused with cupertino-elevate, which transfigures an existing feature's ongoing feel rather than the first-contact sequence."
---

Redesign exactly the first five minutes of first contact — the way unwrapping an Apple product is itself part of the product. Nothing beyond that window is in scope for this technique.

## Steps

1. **Trace the actual sequence** a new user hits today, exactly as it currently happens — not the intended flow, the real one: every screen, prompt, permission request, required signup field, and wait state between "just installed/opened this" and five minutes later. If you haven't verified the real sequence (by reading the actual code path or running it), don't guess at it — go look.
2. **Identify what's revealed first**: does the very first thing the user sees communicate value, or does it front-load friction (forms, permissions, configuration) before any payoff? Name it plainly.
3. **Name the theater moments**: which steps, if any, already do more than function — they communicate the character of the product (a loading animation with personality, copy that sounds like someone wrote it on purpose, a first action that's satisfying rather than merely functional)? Where are theater moments absent that could exist?
4. **Cut or defer anything not earning its place**: for every step in the current sequence, ask whether it must happen in the first five minutes or whether it can be removed entirely or deferred to later (progressive disclosure, deferred permission requests, optional setup skipped by default). List what you removed or deferred and why.
5. **Build the redesigned first-run flow** — production-grade, not a slide deck of the idea.

## Scope discipline

If asked to also improve later onboarding steps (day 2 emails, feature discovery after week one), note that those are out of scope for this technique and either hand them to a different pass or explicitly flag them as deferred. Don't let the first-five-minutes redesign quietly grow into a full onboarding-arc redesign.

## Output format

Actual current sequence → what's revealed first → theater moments (present and missing) → what was cut/deferred and why → the built redesigned flow.
