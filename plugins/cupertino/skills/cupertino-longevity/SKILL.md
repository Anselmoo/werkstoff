---
name: cupertino-longevity
description: "Use at architecture-decision time, together with cupertino-integrate, to evaluate whether an architecture, API surface, or codebase structure can evolve incrementally or will force a future rewrite. Trigger on 'will this scale', 'future-proof this', 'API versioning strategy', 'will I regret this architecture', 'is this extensible', 'migration path', 'plugin system', or any design discussion where long-term evolvability is genuinely at stake — not on routine feature work with no durability question."
---

Judge whether this architecture can evolve, or whether it is quietly building toward a forced rewrite (a "Vista Trap" — a decision that looks fine today but has no incremental path forward, the way Windows Vista's restart-from-scratch approach differed from the unbroken NeXTSTEP → macOS → Apple Silicon line).

## Steps

1. **Vista Trap Table**: list concrete decisions under consideration or already made, and for each, name the specific way it could force a rewrite rather than an incremental upgrade (a hardcoded assumption, a leaky abstraction, a dependency with no exit path).
2. **Evolution Readiness Score** — exactly 6 dimensions, each scored 1–5:
   - API/interface stability
   - Data model flexibility
   - Dependency exit costs
   - Test/characterization coverage of current behavior
   - Deployment/rollback reversibility
   - Team knowledge concentration (bus-factor risk)

   Compute the total mechanically — do not eyeball whether the roadmap is needed:
   ```bash
   echo '{"dimensionScores": [d1, d2, d3, d4, d5, d6]}' | python3 "${CLAUDE_PLUGIN_ROOT}/scripts/validators.py" evolution-score
   ```
   The script rejects any call that doesn't supply exactly 6 integer scores from 1–5, and returns `rosettaRoadmapRequired` computed against the fixed threshold of 18 — total < 18 requires a Rosetta Roadmap, total ≥ 18 must NOT include one. Follow whatever the script returns; do not override it with judgment either direction.
3. **Vista Countdown**: give a dated forecast of when the current decision is likely to force a rewrite if nothing changes, grounded in the specific dimensions that scored lowest.
4. **Top 3 seams to stabilize**: the specific interfaces or boundaries most worth hardening now to buy the most evolvability per unit effort.
5. **Rosetta Roadmap** — only if the script said `rosettaRoadmapRequired: true`. A phased plan (named after Apple's PowerPC→Intel Rosetta translation layer) for migrating off the risky decision incrementally, without a stop-the-world rewrite.

## Distinguish from cannibalization

Before calling anything a Vista Trap, apply the distinguishing test: **could this keep improving incrementally?** If no, it is a Vista Trap (forced, architecturally bad). If yes, and someone is choosing to replace it anyway because a successor could be built better, that is cannibalization territory (`cupertino-cannibalize`) — a deliberate, healthy choice, not a trap. Do not default to calling every replacement decision a Vista Trap.

## When paired with cupertino-integrate

If a specific seam decision is also being evaluated with `cupertino-integrate`, present both readouts side by side, each explicitly attributed ("longevity says X, integrate says Y"). Never average them into one verdict that hides which discipline actually won — a seam can be fine to delegate on integration grounds and still risky on longevity grounds, and that tension is the useful output, not noise to smooth over.
