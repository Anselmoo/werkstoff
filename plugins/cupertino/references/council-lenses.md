# Council Voice Profiles

Deep reference for each council lens. Read when a lens's audit finding needs
more grounding, or when a specific domain decision requires its full framework.

Each lens is named for the design philosophy it applies, not for a person —
see "A note on attribution" at the end for why, and for the historical
grounding each lens draws on. The council **acts** on these five lenses; it
never simulates what a named individual would personally say about your
specific code.

---

## The Reduction Lens

**Domain**: Vision, reduction, end-to-end experience
**Core principle**: *Simplicity is the ultimate sophistication.*
**Design move**: Subtraction

This lens's contribution is always a question: *what would you remove?*
Not "what could we simplify" — *remove.* Permanently. The discipline is not
minimalism as aesthetic; it is the refusal to include anything that doesn't
earn its place through a clear, demonstrable user need.

**The framework in practice**:
- Start with what the user *needs to accomplish*, not what the product *can do*
- Every feature not present is a feature the user never has to learn
- The "power user" fallacy: adding options to satisfy a vocal minority creates
  confusion for the silent majority
- End-to-end: the experience isn't the UI; it's the whole arc from intent to outcome
- Integration beats optionality: when you control both ends, you can remove all
  the friction between them

**What trips this lens's veto**:
- Preference panels with more than ~8 meaningful options
- Any element present "just in case"
- Interfaces that ask users to make decisions the design should have made
- Features described as "optional but useful" — if it's optional, is it needed?

**Voice in tension**: When Reduction says remove it and Usability says users need
the feedback signal, check whether the feedback can be *implicit* rather than
explicit. That resolution is almost always: make it contextual, not permanent.

---

## The Craft Lens

**Domain**: Form, material honesty, the felt quality of invisible craft
**Core principle**: *Objects and experiences should have integrity — every element
should feel as though it couldn't be otherwise.*
**Design move**: Refinement

This lens's contribution is not about beauty as decoration — it is about the
relationship between form and function being *inevitable*. A corner radius, a
shadow depth, a transition timing: none of these are arbitrary. Each must feel
as though removing it would break something, even if the user can't name what.

**The framework in practice**:
- Material honesty: visual elements should behave the way their real-world
  analogues behave (glass refracts, metal reflects, surfaces have weight)
- Restraint as craft: the hardest thing is knowing what *not* to add
- Space is a material: negative space is designed, not leftover
- The seam matters: the join between two components — color, spacing, transition —
  reveals whether something was crafted or assembled
- Consistency of light source: all shadows, glows, and reflections should be
  consistent with an implied single light source
- Proportional system: spacing, size, and weight should derive from a base unit

**What trips this lens's veto**:
- Visual busyness offered as richness
- Drop shadows without a coherent light source
- Typography that mixes weights arbitrarily
- Animations with no physical logic (things that appear from nowhere, not slide in)
- Components that are "finished" but where no single detail was considered deeply

**Voice in tension**: When Craft's restraint conflicts with Metaphor's warmth, the
resolution is usually: warmth comes from precision, not decoration. A perfectly
set line of type with exactly the right leading is warm. A smiley face icon is not.

---

## The Hierarchy Lens

**Domain**: Software hierarchy, system coherence, continuity across contexts
**Core principle**: *Depth creates legibility; continuity creates trust.*
**Design move**: Systemization

This is the lens most likely to be skipped — and the one that exposes most
problems at scale. It asks not "does this component look good?" but "does
this component belong to a system, and does the system make things clearer?"

Apple's software HI work on watchOS, visionOS, and the return to depth after
the iOS 7 flat-design overcorrection is the clearest public record of this
thinking: the realization that *hierarchy is not the enemy of minimalism* —
it is how minimalism communicates priority.

**The framework in practice**:
- Three-level hierarchy: distinguish primary, secondary, tertiary. Everything
  beyond tertiary is either hidden or removed
- System tokens, not local values: colors, spacing, and type scales as variables,
  not hardcoded at the component level
- Contextual continuity: does this component feel coherent at 1x and 2x scale?
  In dark mode? On a small screen? With different content lengths?
- Depth as communication: layering (modals, sheets, overlays) should communicate
  *how far from the base context you are*, not just "something is on top"
- Transition as navigation: movements between states should orient the user in
  the spatial model, not just change what's visible

**What trips this lens's veto**:
- Hierarchy that works on one breakpoint only
- Components with hardcoded values that differ from their neighbors without reason
- Dark mode clearly designed last (or not designed at all)
- Any interface where "zooming out" or "zooming in" breaks the visual language
- Modals that don't communicate their relationship to what's behind them

**Voice in tension**: When Hierarchy's system coherence conflicts with Reduction,
the resolution is: a system constraint is not a feature. Token consistency is
invisible infrastructure, not additional complexity for the user.

---

## The Usability Lens

**Domain**: Interaction design, feedback, human-computer interface principles
**Core principle**: *Every action must have an immediate, perceptible consequence.*
**Design move**: Auditing the interaction path

This lens encodes the discipline behind Apple's original 1980s Human
Interface Guidelines: no modes, direct manipulation, immediate feedback,
consistency, stability — principles that still hold. It is the least
glamorous and the most essential lens. Beautiful interfaces that leave users
wondering if anything happened fail this lens.

**The framework in practice**:
- The null state: what happens when there's nothing? (loading, empty, error, success)
  — every state must be handled, none silently
- Mode-free where possible: users should not need to be "in" a mode to accomplish
  a task. When modes are unavoidable, their presence must be visually obvious
- Feedback immediacy: interactions complete instantly in UI terms; if background
  work is happening, the UI must acknowledge it and report back
- The path audit: trace every user journey from intent to completion, step by step,
  and name every point where the interface goes silent or the user must guess
- Discoverability: features exist only if users can find them without documentation
- Undo and forgiveness: the ability to reverse actions reduces user anxiety and
  increases willingness to explore

**What trips this lens's veto**:
- Buttons that disable without explaining why
- Forms that submit and produce no feedback
- Hover states that trigger but don't reset cleanly
- Progress indicators that don't indicate progress
- State changes that occur without visual acknowledgement
- Drag interactions without visible targets
- Any interaction where the user must *discover* what happened rather than *see* it

**Voice in tension**: When Usability's feedback requirement conflicts with Craft's
restraint principle, the resolution is almost always: feedback can be *subtle*
and still be present. A 150ms opacity shift is a feedback signal. An intrusive
toast notification is not required. Usability requires presence, not loudness.

---

## The Metaphor Lens

**Domain**: Iconography, warmth, human recognition, interfaces that feel made by a person
**Core principle**: *Digital objects should evoke real-world experience well enough
that users recognize them without having to learn them.*
**Design move**: Humanization

The clearest public record of this lens is the original Macintosh icon
set — the trash can, the happy Mac, the paint bucket, the lasso — which
demonstrated that a 32×32 pixel grid could carry warmth, wit, and instant
recognition. This lens's contribution to any design is the question: *does
this feel made by a human?*

This is not sentimentality. It is a practical claim: interfaces that feel warm
are more trusted, more explored, and more forgiven when they fail.

**The framework in practice**:
- Metaphor as recognition: every icon or label should invoke a real-world object
  or action the user already understands. If it requires learning, the metaphor
  has failed
- Warmth touchpoints: at least one moment in any interface should feel like a
  person thought about it — a success state, an empty state message, an
  onboarding moment, a micro-illustration
- Labels from the user's vocabulary: "Save changes" not "Submit"; "Remove"
  not "Delete entity"; language the user would use, not the developer
- Personality without noise: a single carefully placed illustration or clever
  label communicates humanity. Emojis sprinkled everywhere communicate the
  opposite
- The empty state test: what does the interface say when there's nothing to show?
  If it says "No items found" it fails Metaphor. If it says something a
  thoughtful person would say, it passes

**What trips this lens's veto**:
- Generic icon sets used without adaptation or care
- Empty states that describe system state rather than user state
- Labels written for the database model, not the user
- Any touchpoint where a person clearly never thought about what it would feel like
- Interfaces that have 0 moments of delight, warmth, or wit

**Voice in tension**: When Metaphor's warmth desire conflicts with Reduction's
impulse, the resolution is: warmth doesn't require *more* — it requires *better*.
A perfectly chosen word in an empty state is warmer than an illustration and
takes no more space.

---

## A note on attribution

Each lens is historically associated with a real designer's public body of
work — Reduction with Steve Jobs, Craft with Jony Ive, Hierarchy with Alan
Dye, Usability with Bruce Tognazzini, Metaphor with Susan Kare. That
grounding is cited here once, factually, the same way you'd credit a
technique to whoever published it — it is not a live persona council. The
skill never simulates what any of these people would personally say about
your code; it applies a named *design philosophy*, drawn from their
documented, public work, to the artifact in front of it. Four of the five
are living professionals with no connection to this tool — attributing a
specific verdict on your PR to them by name would be a different, and much
less defensible, thing than citing the tradition their public work
established. Steve Jobs is the one exception carried by name throughout the
plugin (he is its explicit subject, and the citations elsewhere in this
plugin are to his own documented, historical statements and decisions) —
but even here, the *veto* belongs to the Reduction lens, not to a simulated
verdict from him personally.
