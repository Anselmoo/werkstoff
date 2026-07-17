# Wire classifier — routing a wire to one of seven proof strategies

`andon-verify` has seven proof strategies (a–g). Given a wire and the fix
proposed for it (from `andon-propose`), this is the explicit decision
procedure for picking which strategy proves it. Routing is a real,
documented artifact here — never implicit or "pick whichever seems
right."

## Inputs to the classifier

1. **The wire's stated type** — `andon-propose` already names a
   recommended strategy in its output (Phase 1, step 3). Start there.
2. **The gap `kind`** (`bug` | `feature` | `wire`, from `andon-loop`'s
   Phase 2 scan).
3. **What crosses the wire** — data/types (structural), numbers
   (numerical), a prose/design claim (epistemic), an autonomous-fix's own
   process (agentic-reliability), a code-structure claim (connectivity),
   an invariant over an input space (property), or an already-passing
   test whose strength is in question (verify-the-verifier).

## Decision flowchart

```
                        ┌─────────────────────────────┐
                        │  What does the fix actually  │
                        │  need proven?                │
                        └───────────────┬───────────────┘
                                        │
        ┌──────────────┬───────────────┼───────────────┬──────────────────┬───────────────────┬────────────────────┐
        │              │               │               │                  │                    │
        ▼              ▼               ▼               ▼                  ▼                    ▼                    ▼
  "Does this      "Are these      "Is this claim   "Did an        "Does this code-   "Does this fix   "Did a passing
   code/artifact    numbers        falsifiable /     autonomous     structure claim    hold across an   wired test
   satisfy the      right?"        does the          fix stay      actually hold —     input space,     actually prove
   contract?"       (solver,       evidence          reliable?"    e.g. does A's       not just one     anything, or
                     fit, sim,      earn the                       export get         known example?"  does it just
                     numerical      claim?"                        referenced by B?"                    execute code?"
                     kernel)
        │              │               │               │                  │                    │                    │
        ▼              ▼               ▼               ▼                  ▼                    ▼                    ▼
   Strategy a     Strategy b     Strategy c      Strategy d        Strategy e          Strategy f          Strategy g
   (tribunal)     (oracle-gap    (epistemic       (agentic          (structural/         (property/          ("verify the
                   V&V)           rubric)          reliability      connectivity,         invariant)          verifier")
                                                    dispatch)        3-tier)
```

## Per-strategy trigger conditions

| Strategy | Fires when | Does NOT fire when |
|---|---|---|
| **a — Tribunal (default)** | The wire is a code/artifact wire with no more specific match below — this is the fallback default, not a last resort of shame. Most `bug`/`feature` gaps land here. | A more specific trigger below matches — prefer the specific strategy over the generic tribunal whenever one applies. |
| **b — Oracle-gap V&V** | The wire crosses a numerical/scientific computation: a solver, a fit, a simulation, any kernel where "is this number right" is the question and there may be no known correct answer to test against. | The wire is about whether code compiles/parses/is well-typed (Rung 0, handled inline, no strategy needed) or is a prose claim (→ c). |
| **c — Epistemic rubric** | The wire is a claim, not code — a design rationale, a research/architecture statement, a "this generalizes" or "this is honest" assertion that needs falsifiability/evidence-grounding, not execution. | The claim is actually a numerical claim with a computable answer (→ b) or a claim about test strength (→ g). |
| **d — Agentic-reliability dispatch** | The gap or fix concerns an *autonomous fix's own reliability* — did the fix that was just auto-applied introduce an unbounded retry, a missing escalation path, or excessive tool scope in some agent/skill/workflow definition. | The fix is ordinary application code with no agentic-loop shape. |
| **e — Structural/connectivity, 3-tier** | The wire is a code-structure claim: "stage A's exported symbol is actually referenced by stage B", "this is the only caller", "the rename propagated everywhere". | The wire is about runtime *behavior* rather than static structure (→ a, or b if numerical). |
| **f — Property/invariant proof** | The wire's contract is expressible as an invariant that must hold across an input space (not one known-answer example, and not LLM judgment) — e.g. "serialize then deserialize is the identity", "sort output is always non-decreasing regardless of input". | The invariant is really about numerical correctness against a scientific model (→ b — b is more specific for that case) or is a single fixed example (→ a is cheaper). |
| **g — Verify the verifier** | A wire already has a "proof" in the form of a passing test, and the question is whether that test would actually catch a regression — contract drift at the stage boundary, or mutation-testing the wired test itself. | No test exists yet to interrogate — write one first (strategy a or b), then g can audit it later. |

## Tie-breaking rules

1. **Specificity beats the default.** Strategy a is the fallback; any of
   b/c/d/e/f/g that matches wins over a.
2. **b beats f beats a** for numerical code — b is the most specific
   (closes the oracle gap with domain-appropriate V&V technique), f is
   more general (any invariant), a is generic LLM judgment. Use the most
   specific strategy whose trigger condition is met.
3. **g is always additive, never a replacement.** If a wire already has a
   proof under some other strategy and the question is "but is that
   proof any good", that's g layered on top of whatever strategy produced
   the original proof — not instead of it. Record both in the wire's
   evidence chain.
4. **Multiple strategies can apply to one wire over its lifetime.** A
   wire proven once by a is not barred from later also getting a g check.
   The classifier picks the strategy for *this* proof attempt, not a
   permanent label on the wire.
5. **When genuinely ambiguous between two non-default strategies**, name
   both candidates in the proposal (`andon-propose`'s "Verification
   strategy" field) and let a human confirm — this is exactly the kind
   of load-bearing fork `andon-propose`'s Phase 2 grill should surface,
   not something `andon-verify` should silently guess at.

## Shared cost model applies after routing

Once a strategy is picked, the Detection Ladder (Rung 0 type-system →
Rung 4 visual+LLM, see the strategy docs and `andon-vocabulary.md`)
governs how expensive a check within that strategy needs to be — climb
only as high as the defect class requires, regardless of which of the
seven strategies is running.
