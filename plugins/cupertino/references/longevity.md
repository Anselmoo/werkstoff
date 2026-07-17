# The Vista Trap and the Rosetta Roadmap

> Apple didn't rewrite macOS. It evolved: NeXTSTEP -> Mac OS X -> Intel ->
> Apple Silicon — one continuous line across roughly 25 years, each
> transition bridged rather than forced. Microsoft shipped Windows Vista, an
> architecture change so disruptive it broke driver and application
> compatibility wholesale, and then had to walk much of it back with
> Windows 7.

## Governing metaphor

The unbroken NeXTSTEP-to-Apple-Silicon lineage is the positive case: every
major platform transition (PowerPC to Intel via Rosetta 1, Intel to Apple
Silicon via Rosetta 2, Objective-C to Swift via ObjC interop) shipped a
bridge that let old and new coexist, rather than forcing a hard cutover. A
"Vista moment" is the negative case — the point where accumulated design
debt forces a stop-and-restart instead of a continue-and-improve, because
some early assumption became a load-bearing wall that can no longer move
without bringing the structure down.

This technique's whole purpose is finding the seeds of a Vista moment
**before they're load-bearing** — while the wall is still cheap to move.

## Diagnostic framework — 4 levels

Run all four levels. Flag each item 🟥 (Vista trap), 🟡 (risk), or 🟢
(evolutionary).

### Level 1 — Interface audit

Examine every public boundary: function signatures, REST endpoints, config
schemas, CLI flags, event payloads, file formats. For each, ask:

- Can I add to this without breaking callers?
- Can I change the implementation without callers noticing?
- What breaks if I rename this? (Leaky naming = tight coupling.)
- Is there a version signal (`/api/v1/`, `version: 2`, semver)?
- Who owns this contract? (If "everyone," it can never change.)

🟥 if changing the interface requires updating callers you don't control, or
there is no versioning strategy at all.

### Level 2 — Dependency direction

Map how components depend on each other. Evolutionary architecture is a DAG;
architecture headed for a rewrite has cycles or an inverted flow.

- Lower-level components importing higher-level ones -> 🟥 inverted
  dependency.
- Concrete implementations importing other concrete implementations -> 🟡
  coupling.
- Everything depending on stable abstractions -> 🟢 evolutionary.
- A "god module" everything imports -> 🟥 Vista nucleus.

### Level 3 — Change-surface analysis

Ask what changes in the next two years, and rate each high-traffic change
vector:

| What changes | Where it should live | Red flag |
|---|---|---|
| Business rules | Top layer only | Embedded in DB schema or infra code |
| Protocol/wire format | Adapter layer | Spread across domain logic |
| External API calls | Anti-corruption layer | Called directly from core |
| Data model shape | Migration-enabled store | Assumed immutable in core |
| Feature toggles | Config/flag layer | Hard-coded booleans |

- 🟢 change is isolated (1 file, 1 module, ~1 day)
- 🟡 change ripples across 2-5 places (~1 week)
- 🟥 change ripples across the codebase (Vista — a quarter, maybe longer)

### Level 4 — Evolution Readiness Score

Score each of 6 dimensions 1-5 (1 = no strategy, 5 = Apple-grade):

| Dimension | Key question | Score |
|---|---|---|
| Interface stability | Are public contracts versioned and stable? | /5 |
| Deprecation lifecycle | Is there a defined path for retiring old behavior? | /5 |
| Migration support | Can old and new versions coexist during transitions? | /5 |
| Layering integrity | Do dependencies flow in one direction only? | /5 |
| Change isolation | Is business logic decoupled from infrastructure? | /5 |
| Extensibility | Can new behavior be added without modifying core? | /5 |

**Total out of 30. Interpretation:**

- **26-30** — macOS trajectory: keep building, refine at the margins.
- **18-25** — Vista risk zones identified: stabilize specific seams.
- **10-17** — a ground-up redesign is in your future: act now, before the
  load-bearing walls multiply.
- **< 10** — already in Vista: apply the Rosetta Roadmap immediately.

The Rosetta Roadmap (below) is triggered whenever the total score is
**below 18** — i.e. both the 10-17 and < 10 bands, not only the worst case.

### Level 5 — the Vista Countdown (dated forecast)

A score is a still photo of something fundamentally about time. Convert it
into a dated forecast, because "18/30" is ignorable but "you have two
quarters" is not:

1. **Name the breaking change** — of all plausible future requirements,
   the one this architecture cannot absorb without a rewrite. Usually a new
   axis of variation the current model treats as fixed: multi-tenancy, a
   second region, a new auth provider, a non-relational data shape,
   real-time where it was batch, a second consumer of a "private" interface.
2. **Locate the wall** — trace exactly which 🟥 trap that request collides
   with, and how far the blast radius spreads.
3. **Date it** — estimate when the request arrives using whatever signal
   exists (roadmap, growth curve, domain trajectory, an explicit user ask).
   Be honest about confidence; a directional date beats no date.

Output as a Vista Countdown: *"The change that breaks you: [X]. It collides
with [trap + location]. At current trajectory you reach it in roughly
[timeframe]. That is your window to apply the Rosetta Roadmap to [the seam]
— starting now, before the wall is load-bearing."* If the score is 26+ and
no plausible breaking change is on the horizon, say so plainly rather than
manufacturing urgency.

## The Rosetta Roadmap (prescription, triggered when total score < 18)

Don't rewrite. Bridge — the way Rosetta ran old binaries on new architecture
transparently, with the user seeing nothing while the migration happened
underneath.

1. **Add an adapter layer** between the legacy interface and the new
   design. Old callers use the adapter; new callers use the clean interface.
   Both work simultaneously.
2. **Deprecate, don't delete.** Mark old paths with a timeline and a
   migration guide. Remove only after adoption is measured and complete.
3. **Dual-write during migration.** The new system writes to both old and
   new stores until trust is established. Rollback stays possible the whole
   time.
4. **Feature-flag the new path.** Gradual rollout, measured at each step.
   Retire the old path only when metrics confirm safety.
5. **Version at the seam, not the whole system.** `/v2/` on one endpoint,
   not a full replatform.

## Apple mechanism -> code equivalent (quick reference)

| Apple mechanism | Code equivalent |
|---|---|
| `@available(macOS 14, *)` | Feature flags, `@deprecated` + timeline |
| Rosetta translation layer | Adapter / anti-corruption layer |
| Universal Binary | Single interface, multiple implementations |
| XPC service boundary | Separate process / microservice with versioned protocol |
| Swift <-> ObjC interop bridge | Foreign function interface, dual-mode API |
| AppKit API stability guarantee | Semantic versioning with LTS commitment |
| DriverKit user-space drivers | Plugin system with stable extension ABI |

## Output format

1. Headline verdict — one sentence: macOS trajectory or Vista risk, and why.
2. Vista Trap Table — 🟥 traps found, exact location and consequence.
3. Evolution Wins — 🟢 things already done well (brief, no false praise).
4. Evolution Readiness Score — filled table with total.
5. Vista Countdown (Level 5) — or "no wall in sight" if 26+.
6. Top 3 Seams to Stabilize — concrete actions, ordered by blast radius.
7. Rosetta Roadmap — only if total score < 18: phased migration plan, old
   and new coexisting at each phase.

## TENSION RULE — read together with integrate.md

This technique is in deliberate tension with `integrate.md`
(`cupertino-integrate`), and the two must never be silently collapsed into
one verdict when both run on the same architecture decision. See
`integrate.md`'s own Tension Rule section for the full statement; in short:
`cupertino-longevity` argues for evolvability (don't let the architecture
force a rewrite), `cupertino-integrate` argues for deliberate tight
ownership (a better experience, at some cost to flexibility) — both
readouts are legitimate, and a real decision needs both surfaced side by
side, not averaged away.

## Distinction from cannibalize.md — same surface symptom, different test

"We're replacing this" can be either a Vista Trap (bad — forced by decaying
architecture, exactly what this document exists to prevent) or a deliberate
cannibalization (good — see `cannibalize.md`). The distinguishing test lives
in `cannibalize.md`; the short version: was the replacement *forced* by a
wall this document would have flagged, or was it *chosen* because the team
could build the successor better than a competitor would? Same words, very
different diagnosis — never assume "we're replacing this" is automatically
either a trap or a triumph without asking which one it is.
