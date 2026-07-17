# The Whole Widget — Vertical Integration by Choice

> "People who are serious about software should make their own hardware."
> — Alan Kay

Jobs quoted this line approvingly and, more importantly, lived by it: Apple's
recurring, deliberate bet across its history is owning the whole stack —
hardware, operating system, and (increasingly) services — rather than
delegating any layer of it to a third party. The Apple II, the original
Macintosh, the iPod-plus-iTunes pairing, the iPhone-plus-App-Store-plus-Apple
Silicon stack: in each case Apple chose to build and control a layer that
competitors were content to leave to a partner, specifically because
controlling it let them remove friction at the seam between layers that
nobody who didn't own both sides could remove.

This is "the whole widget": treat hardware and software (or, in a software
project, treat two adjacent layers of your own stack) as one integrated
product to be designed together, rather than as independent components each
optimized in isolation and stitched together at the interface.

## What vertical integration actually buys, and what it costs

**Buys:**
- Removing friction that only exists *because* two layers are owned by
  different parties with different incentives and different release
  cadences.
- A better, more coherent experience at the seam — fewer compatibility
  matrices, fewer lowest-common-denominator compromises, tighter
  performance/battery/reliability tuning across the boundary.
- The ability to ship a capability that literally isn't possible when the
  layers are owned separately, because it requires co-design.

**Costs:**
- Flexibility. A tightly owned stack is harder to swap a layer out of later
  — the "just replace the database" or "just switch cloud providers" move
  gets more expensive the more the layers above and below have been
  co-designed around each other's specifics.
- Surface area. Owning more of the stack means owning more of the
  maintenance, more of the failure modes, more of the expertise required.
- Optionality for the user/customer, in some cases — a fully integrated
  stack can mean fewer places for a third party to plug in.

Vertical integration is not free virtue — it is a deliberate trade of
flexibility for a better experience at a specific seam, made because the
seam is judged worth owning. This document exists to make that trade
**explicit** rather than accidental.

## Applying it in software work

This runs **at architecture-decision time**, alongside `cupertino-longevity`
(see the Tension Rule below — they are companions run together, not
alternatives).

1. **Name the candidate seam.** Which boundary is under discussion: your
   own service vs. a third-party API, your own auth vs. an identity
   provider, your own rendering layer vs. a UI framework, your own storage
   vs. a managed database, your own protocol vs. an open standard?
2. **Ask what friction exists at that seam today, or will exist as the
   product matures.** Version skew, lowest-common-denominator feature
   support, latency from crossing a network/process boundary that owning
   both sides could collapse, an experience compromise neither side alone
   can fix.
3. **Ask whether owning both sides of the seam removes that friction in a
   way delegation cannot.** If the friction is inherent to the *problem*
   (e.g. genuine network partition tolerance) rather than to *divided
   ownership*, vertical integration doesn't buy anything — don't reach for
   it reflexively.
4. **State the trade explicitly.** If integration is chosen: name exactly
   what flexibility is being given up, and confirm the team is choosing
   that cost deliberately, not discovering it later as a surprise. If
   delegation is chosen: name exactly what friction is being accepted at
   the seam, and confirm it's tolerable given the product's actual
   requirements.
5. **This is a deliberate call, not a default.** Apple did not vertically
   integrate everything — it uses commodity components (memory, some
   chipsets, foundry manufacturing) where the seam friction doesn't matter
   enough to justify owning it. The discipline is judgment per seam, not a
   blanket "always own more of the stack."

## TENSION RULE — read together with longevity.md

`cupertino-integrate` is **in deliberate tension** with `cupertino-longevity`
(`longevity.md`), and this tension must be **surfaced, never silently
collapsed into one verdict**, whenever both skills run on the same
architecture decision (which `cupertino-review`'s pipeline does by design —
see its Step 3 in `SKILL.md`).

- **`cupertino-longevity`** argues from evolvability: don't let today's
  architecture force tomorrow's rewrite. Its instinct, applied to a seam, is
  to keep it loosely coupled, versioned, and swappable — an adapter layer at
  the boundary, because coupling is the thing that turns into a Vista Trap.
- **`cupertino-integrate`** argues from experience quality: some seams are
  worth owning tightly *right now*, even at the cost of making that seam
  harder to swap out later, because the tight coupling is what removes the
  friction and delivers the better experience.

Both positions are legitimate, and they pull in genuinely opposite
directions on the same seam. When `cupertino-review` reaches Step 3 and runs
both skills against the same architecture decision, **present both readouts
side by side, explicitly attributed** — "longevity says X, integrate says Y"
— and let the resolution be a stated, reasoned trade-off (which one wins for
*this* seam, and why), never a single averaged-out recommendation that hides
which discipline actually won. A decision that silently picks one side
without naming the tension it overrode has not applied this technique
correctly, even if the outcome happens to be right.

A useful diagnostic for which side should generally win on a given seam:
if the seam is customer-facing and central to the product's actual
differentiation, integrate's case gets stronger. If the seam is
infrastructure-adjacent, likely to face a real future requirement
(multi-tenancy, a second provider, a new platform), longevity's case gets
stronger. This is a heuristic, not a formula — state the actual reasoning
for the seam under discussion, don't just cite the heuristic.
