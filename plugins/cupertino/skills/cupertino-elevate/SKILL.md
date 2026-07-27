---
name: cupertino-elevate
description: "Use at build-time, ONLY when a low-status commodity feature already in scope for the current build — error messages, logs, config, settings, onboarding, migrations, loading states, empty states, backups, status output — could be transfigured into something beloved, the way Apple turned boring backup into Time Machine. Trigger on 'this feature is boring', 'nobody uses this', 'make this delightful', 'elevate this'. Never seek out a commodity feature independently or apply this to a brand-new capability not already being worked on — if nothing already in scope qualifies, say so and skip."
---

Transfigure an existing, already-in-scope commodity feature. This is never about adding new capability — the function already exists; what changes is the metaphor, the visibility, and the felt experience until its status flips from chore to showpiece.

## Scope check — do this first

Confirm the feature is (a) already in scope for the current build, and (b) genuinely low-status/commodity today. If it's a brand-new capability nobody was already building, this technique does not apply — say so plainly and stop rather than inventing a feature to elevate.

## Steps

1. **Name the commodity function and its dullness-root**: what it actually does mechanically, and specifically why it currently feels like a chore (invisible, punitive, unexplained, purely defensive).
2. **Find the human metaphor**: one sentence naming a familiar human concept that reframes this function — the thing that let backup become "a time machine" rather than "a copy job."
3. **Describe the transfiguration**: how the metaphor changes visibility (can you see it happening?), navigability (can you move through it, not just trigger it once?), and delight (does using it feel good, not just safe?).
4. **Status-flip check**: would the person using this actually want to screenshot it, demo it to a colleague, or mention it unprompted? If you can't articulate a real reason they would, the transfiguration hasn't gone far enough yet — go back to step 3, don't ship a half-measure.
5. **Ship the one transfiguration fully.** Do not dilute it by bundling in adjacent improvements ("while I'm in here, let me also fix the settings page") — one commodity feature, fully transfigured, is the deliverable. Adjacent improvements are separate work.
6. **Build it**: production-grade redesigned feature, not a mockup.

## Output format

Scope check → commodity function + dullness-root → metaphor → transfiguration description → status-flip check → the built feature. If the scope check fails, stop there and say why nothing in scope qualifies.
