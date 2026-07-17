# Tension Resolution Case Library

Common conflicts between council lenses, with documented resolutions.
Use this when Step 3 surfaces a tension and the resolution isn't obvious.

---

## Format

Each case:
- **Conflict**: which lenses, what they each want
- **Resolution**: the principled outcome
- **Pattern**: the generalizable rule

---

## Case 1: Reduction vs. Usability — Removal vs. Feedback Signal

**Conflict**  
Reduction wants to remove a status indicator (e.g., a "saving..." message, a loading
spinner, a confirmation toast). It feels like clutter. Usability requires it — without
it, the user has no confirmation that their action was received.

**Resolution**  
Keep the signal; make it *contextual and transient*, not permanent. A 150ms
opacity pulse on the element being acted on is a Usability-compliant signal that
Reduction can live with. Persistent status panels are not required.

**Pattern**  
*When Reduction and Usability conflict over presence vs. absence of a UI element: the
element stays if it answers a user question; it goes if it only confirms
system state the user doesn't need to know.*

---

## Case 2: Craft vs. Metaphor — Restraint vs. Warmth

**Conflict**  
Craft's restraint principle pushes toward sparse, precise, unadorned interfaces.
Metaphor's warmth principle wants a moment — an illustration, a clever empty state,
a personality touch — that makes the interface feel human.

**Resolution**  
Warmth doesn't require decoration; it requires *intention*. A perfectly chosen
word in an empty state is warmer than a generic illustration. The resolution is
to find the warmth in the language, the transition, or the spacing — not in
adding visual elements.

**Pattern**  
*When Craft and Metaphor conflict: look for warmth through craft (word choice, timing,
proportion) before adding visual elements. Craft's restraint and Metaphor's warmth
are not opposites — the most sophisticated Metaphor moments are the most Craft-like
ones.*

---

## Case 3: Hierarchy vs. Reduction — System Coherence vs. Reduction

**Conflict**  
Hierarchy wants token consistency, a proper color system, responsive hierarchy — all
of which feel like complexity Reduction would remove. Reduction says: ship the thing,
don't build a design system.

**Resolution**  
System infrastructure is invisible to the user. Token consistency adds zero UI
elements — it only constrains the developer. Reduction's reduction applies to *user-
visible complexity*, not to the engineering discipline underneath. A component
can be maximally simple to use and still be built on a coherent token system.

**Pattern**  
*Hierarchy vs. Reduction tensions are usually false conflicts: Reduction removes user-facing
complexity, Hierarchy constrains developer-facing implementation. They rarely conflict
in practice; if they appear to, check whether the "system complexity" Hierarchy is
asking for is actually user-visible.*

---

## Case 4: Usability vs. Craft — Feedback Loudness vs. Visual Restraint

**Conflict**  
Usability requires feedback for every action. Craft's restraint principle resists
adding visual noise — loading spinners, toast notifications, alert banners.

**Resolution**  
Feedback granularity: Usability requires *presence*, not *loudness*. A subtle state
change on the affected element (opacity, color shift, micro-movement) satisfies
Usability. A full-screen overlay does not satisfy Craft. The resolution is:
- Use the most local, smallest signal that still communicates clearly
- Reserve loud signals (modals, toasts, banners) for irreversible actions
- Never use no signal at all

**Pattern**  
*Usability requires that users see what happened. Craft requires it not be visually
invasive. The resolution is always: find the quietest signal that still
communicates. Locality and transiency reduce visual noise while preserving
feedback integrity.*

---

## Case 5: Reduction vs. Metaphor — Feature Removal vs. Warmth Touchpoint

**Conflict**  
Reduction wants to remove the empty state illustration or the success animation — it
feels extraneous. Metaphor says removing it makes the interface feel dead and cold.

**Resolution**  
Warmth touchpoints occupy no meaningful user attention *unless they are placed
at the wrong moment*. An empty state illustration that appears when a user first
lands in a new section is a Metaphor moment. The same illustration reappearing on
the 50th visit is noise. The resolution: warmth touchpoints are *contextual* —
shown once or in moments of genuine significance, not as permanent furniture.

**Pattern**  
*Reduction removes features that users interact with repeatedly; Metaphor moments are
often one-time or rare occurrences. Check the frequency of the touchpoint. If
it's rare enough to be surprising, Reduction won't veto it.*

---

## Case 6: Hierarchy vs. Metaphor — System Coherence vs. Local Warmth

**Conflict**  
Metaphor wants a whimsical success animation or a personality-driven empty state.
Hierarchy says it breaks the visual language of the system — the system is serious
or minimal, and this warmth moment is out of register.

**Resolution**  
The warmth moment must be *calibrated to the system's register*. In a surgical,
enterprise-grade system, warmth is a perfectly written error message, not a
confetti burst. In a consumer product, warmth can be playful. Hierarchy sets the
register; Metaphor finds warmth within it.

**Pattern**  
*Hierarchy defines the emotional register of the system. Metaphor finds humanity within
that register, not outside it. There is warmth appropriate to every tone — the
council's job is to find the Metaphor move that Hierarchy would approve.*

---

## Case 7: Craft vs. Hierarchy — Local Craft vs. System Standardization

**Conflict**  
Craft wants to craft a specific component with careful, unique proportions —
a custom shadow, a distinctive animation, a bespoke color treatment. Hierarchy says
the component must use the system tokens and can't introduce new visual variables.

**Resolution**  
Craft's craft should operate *within the token system*, not around it. The craft
shows in *how* tokens are applied — the relationships between values, the
animation curve, the spatial rhythm — not in introducing new values. A
beautifully crafted component and a token-consistent component are not in
conflict; a component that uses arbitrary hardcoded values to achieve beauty
is an Craft failure (it can't be maintained) and a Hierarchy failure (it breaks
coherence).

**Pattern**  
*Craft's craft is in the application of a system, not the creation of exceptions
to it. When Craft and Hierarchy appear to conflict, the real question is: can the craft
be expressed within the constraints? Almost always: yes.*

---

## Case 8: Usability vs. Reduction — Feature Discovery vs. Feature Absence

**Conflict**  
Usability wants affordances that make features discoverable — visible hints, labels,
hover states, progressive disclosure. Reduction wants those affordances removed as
clutter — the interface should be direct, not annotated.

**Resolution**  
Discovery affordances should be *contextual*, not permanent. Usability is satisfied
by a hover state or a first-run highlight; Reduction is satisfied if those hints
disappear after the user has encountered the feature once. The resolution: use
progressive disclosure that retires itself. First-visit affordances are Usability-
compliant; permanent training wheels are Reduction's veto.

**Pattern**  
*Usability requires discoverability; Reduction requires it not be permanent infrastructure.
The resolution is: contextual, one-time, or hover-state affordances. Never
permanent visual hints for features a returning user already knows.*
