# Transfiguration — Boring to Brilliant

> Backup was the most boring feature on any computer. Apple turned it into
> Time Machine — you fly backward through space, windows receding down a
> tunnel of stars, a timeline on the edge. Same feature. Point-in-time
> restore. Apple changed nothing about *what it did* and everything about
> *what it felt like*.

## Transfiguration, not addition

This is the opposite move from `cupertino-reveal`:

- **`cupertino-reveal`** *adds* a capability that wasn't there. The
  surprise is "I didn't know I needed this."
- **`cupertino-elevate`** *transfigures* a capability that's already there
  and dull. Nothing new is added to what it does. The surprise is "I can't
  believe *that* is the coolest thing here."

This technique applies to exactly **one already-existing, low-status
feature — never a new feature.** If the output of applying this technique
is a proposal for a new capability, that's the wrong technique; the whole
discipline is: the function stays the same, the experience is reborn.

## The method

### Step 1 — Name the commodity function

Identify the necessary, low-status thing already in scope. In software
these are the usual suspects — abstract, invisible, deferred, or framed as
a chore:

| Commodity function | Why it's dull | Transfigured example |
|---|---|---|
| Compiler/runtime errors | A wall of stack trace | Elm-style errors that teach and point at the fix |
| Logs | Grey text scrolling past | Colorized, structured, navigable; streamed like a story |
| Config files | Raw YAML edited blind | Guided `init` wizard with live validation |
| Settings | A list of toggles | Grouped, searchable, instant visible effect |
| Onboarding | A modal you dismiss | An interactive playground you *do* instead of read |
| Migrations | Scary, irreversible SQL | A visual, reversible timeline you can scrub |
| Test output | Pass/fail dots | Beautiful diffs, progress with personality |
| `git log`/history | Flat text list | A navigable graph |
| Loading/empty states | A spinner, a blank box | Skeleton screens, an empty state that teaches |
| 404/error pages | Dead end | A memorable, on-brand moment |
| Backup | Invisible, ignored | **Time Machine** |

### Step 2 — Diagnose why it's dull

Name the specific root:

- **Invisible** — the work happens but is never seen (backup, caching).
- **Abstract** — the concept has no physical analogue (point-in-time
  restore).
- **List-shaped** — presented as flat text/rows when it has richer
  structure.
- **Deferred** — framed as something to do *later*, so never loved.
- **Chore-framed** — presented as an obligation, not a capability.

### Step 3 — Find the human metaphor

The heart of the technique. Time Machine's genius was the metaphor: restore
became time travel, made spatial and navigable.

1. What real-world thing is this actually like? Restore -> going back in
   time. Logs -> a story unfolding. Migration -> moving house. Dependency
   graph -> a map.
2. Can it be made spatial or temporal? Humans navigate space and time
   natively — turning an abstract operation into a place you move through,
   or a timeline you scrub, is the single most reliable transfiguration.
3. What would make someone *want* to trigger it? If the answer is
   "nothing," the metaphor isn't strong enough yet.

A good metaphor is **load-bearing**: it makes the feature easier to
understand *and* more delightful at the same time. If it only decorates,
it's lipstick — discard it and keep looking.

### Step 4 — Make it visible and tangible

- Surface the invisible — show the process happening.
- Make it navigable — let the user move through it (scrub, zoom, step,
  rewind).
- Give immediate feedback — every action has a visible, satisfying
  consequence.
- Respect the metaphor everywhere — naming, motion, sound, and color all
  reinforce the one idea.

### Step 5 — The status-flip test

The only success criterion that matters:

> **Does the feature go from "thing you avoid" to "thing you'd show a
> friend"?**

If a user wouldn't screenshot it, demo it, or mention it unprompted, it
isn't transfigured yet — it's just tidier. Go back to step 3 and find a
stronger metaphor.

### Step 6 — Build it

Don't describe the transfiguration — ship it. Build the *one*
transfiguration fully; don't dilute it with adjacent improvements. Match the
project's existing stack and conventions exactly.

## Applying it in software work

Runs **at build-time**, applied to a commodity feature already in scope
(not sought out independently — see `cupertino-review`'s pipeline notes on
when to reach for this vs. skip it). A good trigger is any moment the team
is already touching a low-status feature for an unrelated reason (a bug fix,
a refactor) — that's the cheapest moment to also ask whether it deserves
transfiguration.

## Output format

1. The commodity — the dull feature in one sentence, and which
   dullness-root (step 2) it suffers from.
2. The metaphor — the human/real-world idea being mapped onto it, one
   sentence. This is the reveal.
3. The transfiguration — how the metaphor makes it visible, navigable, and
   delightful (2-4 sentences).
4. Status-flip check — one line: why a user would now show this to a
   friend.
5. The build — the actual redesigned feature, shipped.

## Distinction from cupertino-unbox — kinship, not overlap

`cupertino-unbox` is closely related (both are Apple-style transfiguration
of something mundane into something memorable) but is kept as a **separate**
technique and must not be merged with this one:

- **`cupertino-elevate`** is general-purpose — any already-existing,
  mid-life commodity feature, anywhere in the product, at any point in its
  lifecycle.
- **`cupertino-unbox`** is specific to exactly one moment: first contact —
  install, first-run, onboarding, the first five minutes. It runs at a
  fixed lifecycle point (build/finishing-time, just before ship), not
  opportunistically whenever a commodity feature is being touched.

If the feature under discussion *is* the first-run/onboarding/install
experience, reach for `cupertino-unbox` instead — its dedicated framing
(the box is the first experience, packaging-as-theater) fits that moment
more precisely than this technique's general commodity-feature framing.
