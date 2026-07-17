# The Box Is the First Experience

> Apple's iPhone and iPad packaging is one of the most well-documented
> examples of unboxing-as-theater in consumer product history: the specific
> weight and resistance of the lid as it lifts, the layered reveal (device
> first, cables and documentation tucked beneath), the precision-cut foam or
> molded trays that hold everything in an exact, deliberate position. None
> of this is packaging as an afterthought — it is treated as a designed
> **experience**, on the theory that the box is the first thing a customer
> touches and therefore the first real impression of the product's whole
> character, before a single feature has been used.

## The software equivalent

Treat **first-run, onboarding, and install** — specifically the first five
minutes of contact with the software — as theater, with the same
deliberateness Apple applies to a physical box: sequencing, pacing, and
what's revealed first are all decisions, not defaults left to whatever
order a framework's scaffolding happens to produce.

This is a narrower target than "onboarding" in the generic UX sense. It is
specifically:

- **Install** — the moment someone runs the installer, `pip install`,
  `npm install`, `docker run`, or downloads the app.
- **First-run** — the very first launch, before any user data or
  configuration exists.
- **Onboarding** — the guided path (if any) from first-run to the user's
  first genuinely useful action.

## The method

### Step 1 — Trace the actual first five minutes, as it exists today

Walk the real sequence a new user hits, in order, exactly as it currently
happens — not the intended sequence, the actual one. Note every screen,
prompt, error possibility, wait, and default. Most first-run experiences
accrete unplanned: a permission dialog here, a config-file requirement
there, an unstyled terminal wall of text, each added independently by
whoever built that particular piece, with nobody ever looking at the
sequence as a whole.

### Step 2 — Identify what's revealed first, and whether that's a choice

Apple's packaging always shows the device itself first — not the charger,
not the manual. What does the software's first-run sequence show first?
Is it the thing the user actually came for, or is it setup friction
(a config file, a login wall, an empty dashboard with nothing in it yet)?
If the first thing shown is friction rather than value, that is the single
highest-leverage thing to fix — the software equivalent of putting the
cable box on top of the phone.

### Step 3 — Find the theater, not just the function

Every step in the sequence has to function (it has to actually install,
actually authenticate, actually configure) — but function alone is not the
bar. Ask, for each step: does this moment communicate the product's
character, or is it purely mechanical? A progress bar is purely mechanical.
A progress bar that shows *what's actually happening* in language a person
would use, paced so the reveal feels considered rather than rushed, is
theater. The goal is not to add delay — Apple's unboxing is precise, not
slow — it's to make the necessary steps communicate something, the way the
lid's resistance communicates precision before the customer has even opened
the box.

### Step 4 — Remove anything that isn't earning its place in the first five
minutes

Apple's box contains the device, a cable, and minimal paper — not a
manual, not accessories nobody asked for. Apply the same discipline: does
every screen, prompt, and required action in the first-run sequence
actually need to happen *now*, in the first five minutes, or can it be
deferred to the moment it's actually needed? A setup wizard that front-loads
every possible configuration option before the user has done anything real
is the unboxing equivalent of a box stuffed with accessories nobody asked
for.

### Step 5 — Build it

Ship the redesigned first-run sequence as real, working onboarding flow —
not a slide describing what it should feel like. Match the project's actual
stack.

## Output format

1. The current sequence — the real first-five-minutes walk from step 1,
   as it exists today.
2. What's revealed first, and whether it's value or friction (step 2).
3. The theater moments — which steps were purely mechanical and how they
   now communicate character (step 3).
4. What got removed or deferred (step 4).
5. The build — the actual redesigned first-run flow, shipped.

## Distinction from cupertino-elevate — kinship, not overlap

See `elevate.md`'s own "Distinction from cupertino-unbox" section for the
full statement. In short: `cupertino-elevate` is general-purpose
transfiguration of any mid-life commodity feature; `cupertino-unbox` is
specifically the first-contact moment, and runs at a fixed lifecycle point
rather than opportunistically. Don't use this technique on a mid-life
settings page just because it happens to also be "dull" — that's
`cupertino-elevate`'s territory.

## Where this sits in the cupertino lifecycle

Runs at build/finishing-time — after the core feature work
(`cupertino-council`, `cupertino-prototype`, `cupertino-elevate`) has
produced something worth a new user's first five minutes, and before
`cupertino-reveal`'s ship-time single addition. Applying this technique to
an install/onboarding flow that isn't otherwise finished yet just polishes
a moving target.
