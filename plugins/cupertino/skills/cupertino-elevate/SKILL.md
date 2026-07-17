---
name: cupertino-elevate
description: >
  Takes a dull, low-status, already-existing commodity feature and
  transfigures it into the signature, beloved part of the software — the way
  Apple turned boring backup into Time Machine. TRANSFIGURATION, not
  addition: the capability already exists; only the metaphor, visibility, and
  experience change, judged by the status-flip test ("would someone
  screenshot it?"). ALWAYS use when the user says a feature is "boring",
  "just a utility", "nobody uses it", "make this exciting", "make this
  delightful", "elevate this", "Time Machine treatment", "boring to
  brilliant", or points at a commodity part of a tool — error messages, logs,
  config, migrations, loading/empty states, 404s, backups — wanting it loved.
  Use at build-time, on a commodity feature already in scope (never a new
  feature). Distinct from cupertino-unbox, which is only the first-
  run/onboarding moment.
---

Nothing new is added to what the feature does; everything about what it
feels like is reborn. Full method (the human-metaphor step is the heart of
it), the commodity-function table, and the status-flip test all live in
`../../references/elevate.md` — read it in full before applying this
technique.

## When to use

Runs at **build-time**, applied to a commodity feature already in scope —
not sought out independently. The cheapest trigger moment is when the team
is already touching a low-status feature for an unrelated reason (a bug
fix, a refactor); that's when asking "does this deserve transfiguration" is
nearly free.

## Process

1. **Name the commodity function** — the necessary, low-status thing
   already in scope. See `../../references/elevate.md`'s table of usual
   suspects (errors, logs, config, settings, onboarding, migrations, test
   output, history, loading/empty states, 404s, backup) for the pattern,
   but the target here is whatever's actually in scope, not that table.
2. **Diagnose why it's dull** — invisible, abstract, list-shaped, deferred,
   or chore-framed. Name the specific root.
3. **Find the human metaphor.** What real-world thing is this actually
   like? Can it be made spatial or temporal? What would make someone want
   to trigger it? A good metaphor is load-bearing — it makes the feature
   both easier to understand and more delightful. If it only decorates,
   it's lipstick; discard it and keep looking.
4. **Make it visible and tangible** — surface the invisible, make it
   navigable, give immediate feedback, respect the metaphor everywhere
   (naming, motion, sound, color).
5. **Run the status-flip test.** Does the feature go from "thing you avoid"
   to "thing you'd show a friend"? If a user wouldn't screenshot it, demo
   it, or mention it unprompted, it isn't transfigured yet — return to
   step 3.
6. **Build it.** Ship the *one* transfiguration fully; don't dilute it with
   adjacent improvements. Match the project's existing stack and
   conventions exactly.

## Output

1. The commodity — one sentence, plus which dullness-root it suffers from.
2. The metaphor — one sentence. This is the reveal.
3. The transfiguration — how the metaphor makes it visible, navigable, and
   delightful (2-4 sentences).
4. Status-flip check — why a user would now show this to a friend.
5. The build — the actual redesigned feature, shipped.

## Relationship to cupertino-reveal — opposite move

`cupertino-reveal` *adds* a capability that wasn't there. `cupertino-
elevate` *transfigures* a capability that's already there and dull. If
you're proposing a new capability, that's `cupertino-reveal`, not this
technique.

## Distinction from cupertino-unbox — kinship, not overlap

`cupertino-unbox` is closely related but stays separate: this technique is
general-purpose, any mid-life commodity feature, applied opportunistically.
`cupertino-unbox` is specific to first contact — install, first-run,
onboarding, the first five minutes — and runs at a fixed lifecycle point
(build/finishing-time, just before ship). If the feature under discussion
*is* the first-run/onboarding/install experience, use `cupertino-unbox`
instead; see `../../references/elevate.md`'s "Distinction from
cupertino-unbox" section for the full statement.
