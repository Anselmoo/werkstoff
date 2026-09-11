# Motion — reference vocabulary

Companion to `visual-asset-taxonomy.md`. Working vocabulary for naming motion
decisions. Motion is the dimension most often left out of a design system and
then invented per component, which is why it drifts faster than any other.

**Kind legend:** `token` — a stored value; `derived` — computed; `rule` — a
constraint needing an anti-rule; `property` — observed, not stored.

---

## Contents

- [Time](#time)
- [Curves](#curves)
- [What actually moves](#what-actually-moves)
- [Patterns](#patterns)
- [Principles worth encoding as rules](#principles-worth-encoding-as-rules)
- [Accessibility](#accessibility)
- [Delivery](#delivery)
- [Frequently confused pairs](#frequently-confused-pairs)
- [Decoding notes](#decoding-notes)

---

## Time

| Term | What it names | Kind |
|---|---|---|
| Duration | How long a change takes | token |
| Duration ramp | The permitted set, named rather than numbered: instant / fast / moderate / slow / deliberate | token |
| Delay | Time before a change begins | token |
| Stagger / cascade | The delay increment applied across a set, so a list arrives as a sequence rather than a block | token |
| Choreography | The coordination of several elements moving at once | rule |
| Sequence vs. parallel | Whether motions follow or overlap | rule |

## Curves

| Term | What it names | Kind |
|---|---|---|
| Easing / timing function | The rate of change over the duration | token |
| `ease-out` | Fast start, slow finish — for things arriving | token |
| `ease-in` | Slow start, fast finish — for things leaving | token |
| `ease-in-out` | For things moving between two on-screen positions | token |
| `cubic-bezier` | The four-number definition of a custom curve | token |
| `linear()` | CSS easing that approximates an arbitrary curve, including a spring | token |
| Spring | Physical model with stiffness, damping and mass; has no fixed duration, which is why it cannot be expressed as a duration token | token |
| Easing set | The small closed set of curves a system permits | token |

## What actually moves

| Term | What it names | Kind |
|---|---|---|
| Transform | translate, scale, rotate — composited, cheap | property |
| Opacity | Fade — composited, cheap | property |
| Layout property | width, height, top, margin — triggers layout on every frame, expensive | rule |
| Distance / travel | How far something moves; belongs in a ramp of its own | token |
| Clip / reveal | Uncovering rather than moving | property |
| Morph | One shape becoming another | property |
| Compositor layer | The GPU-handled surface a transform animates on | property |

## Patterns

| Term | What it names | Kind |
|---|---|---|
| Enter / exit | Appearance and disappearance; asymmetric by design | rule |
| State transition | Movement between two states of one element | rule |
| Shared element transition | One element persisting visually across two views (View Transitions API; "hero transition" elsewhere) | rule |
| Micro-interaction | Small feedback bound to one input | property |
| Feedback motion | Confirmation that input was received — the one motion class that must survive reduced-motion | rule |
| Loading, determinate | Progress with a known end | property |
| Loading, indeterminate | Activity without a known end | property |
| Skeleton / shimmer | Structure shown before content | property |
| Ambient / loop | Continuous motion with no trigger | rule |
| Parallax | Layers moving at different rates with scroll | rule |
| Scroll-driven animation | Progress bound to scroll position rather than time (CSS `animation-timeline`) | property |
| Attention / nudge | Motion used to direct the eye | rule |

## Principles worth encoding as rules

| Principle | Statement |
|---|---|
| Easing asymmetry | Things arriving decelerate (`ease-out`); things leaving accelerate (`ease-in`). Symmetric easing on enter and exit is the most common motion mistake. |
| Distance–duration coupling | Longer travel needs longer duration. One duration applied to every distance reads wrong at both ends. |
| Origin | Motion emanates from what triggered it. A menu opens from its button, not from the screen edge. |
| Continuity | If an element persists between two views, it should move rather than disappear and reappear. |
| Hierarchy | The important element moves last, or moves most. Everything moving equally communicates nothing. |
| Cause | No motion without a cause. Ambient motion is a deliberate exception and needs its own justification. |

**Perception bands**, conventional rather than measured, and worth writing down
as the thresholds motion is checked against: below roughly 100 ms reads as
instant; 100–300 ms reads as responsive; beyond about 400 ms begins to read as
sluggish; beyond a second, an indeterminate indicator is needed instead. Treat
these as the reference lines on a duration chart, not as findings.

## Accessibility

| Term | What it names | Kind |
|---|---|---|
| `prefers-reduced-motion` | The OS-level request for less motion. Non-optional. | rule |
| Reduced-motion substitution | What replaces a motion — usually a fade or an instant change, never nothing, because feedback must survive | rule |
| Vestibular trigger | Large-area movement, parallax, and zoom; the specific classes that cause physical symptoms | rule |
| Flash threshold | No more than three flashes per second (WCAG 2.3.1) | rule |
| Pause / stop control | Required for anything that moves for more than five seconds without user control (WCAG 2.2.2) | rule |

## Delivery

| Term | What it names | Kind |
|---|---|---|
| CSS transition | A change between two states | property |
| CSS animation / keyframes | A defined sequence, loopable | property |
| WAAPI | The Web Animations API; scriptable, interruptible | property |
| FLIP | First-Last-Invert-Play — animating a layout change using transforms only | rule |
| Lottie / Rive | Vector animation formats for authored motion | property |
| SVG SMIL | Older in-SVG animation; poorly supported, avoid | property |
| `will-change` | A hint to promote an element to its own layer; costly if left on | rule |
| Frame budget | Roughly 16.7 ms per frame at 60 Hz; exceeding it produces jank | property |

---

## Frequently confused pairs

**Duration vs. perceived speed.** Two motions of identical duration feel
different at different easings. Tuning duration when the curve is the problem is
the usual dead end.

**Easing vs. spring.** A spring has no duration — it has stiffness, damping and
mass, and settles when it settles. A system that stores only durations cannot
express springs, and a system that stores both needs to say which components use
which.

**Transition vs. animation.** A transition needs a state change to react to; an
animation runs on its own. Loading indicators are animations, hover effects are
transitions, and conflating them produces spinners that stop when nothing is
hovered.

**Stagger vs. delay.** Delay is one number applied to one element. Stagger is an
increment applied across a set. Storing a stagger as a list of delays is how the
increment gets lost.

**Reduced motion is not no motion.** Removing feedback leaves the user unsure
whether input registered. The rule is *substitution*, not deletion.

**Transform vs. layout property.** Animating `width` or `top` recalculates
layout every frame; `transform` does not. This is a correctness constraint, not
a performance preference, and it belongs in the lexicon as an anti-rule.

---

## Decoding notes

- **Duration and easing — grade B.** Declared in `transition` and `animation`
  shorthand and usually the easiest motion facts to extract from a reference.
- **Spring parameters — grade C or absent.** Unless expressed via `linear()`,
  they live in JavaScript or a native framework and are not recoverable from CSS.
- **Stagger increment — grade C.** Requires frame-counting a screen recording.
- **Distance — grade B** from transform values, grade C from a recording.
- **Timing by eye — grade C, always.** This is exactly the case already blocked
  in the derivation report: `motion.duration.enter`, "~250 ms timed by eye from a
  screen recording". A value read off a recording is an open question, not a
  token. Corroborate against declared CSS or carry it to the brief.
- **Perception bands — not from the reference at all.** They come from the
  literature and are the thresholds you check against, not measurements you take.

**Motion uses the same threshold chart as contrast**, with different
parameterisation: measured duration on a linear axis, reference lines at the
perception bands, one series per motion class. A duration sitting just past 400
ms is a different problem from one at 900 ms, and a table saying "slow" for both
flattens that difference in exactly the way the contrast table flattens 3.84
against 2.89.
