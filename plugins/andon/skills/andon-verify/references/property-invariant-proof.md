# Strategy f: property/invariant proof

For wires whose contract naturally reads as "for all inputs matching X,
property Y holds" rather than a single worked example.

## Real tooling only -- mandatory

Use an established property-based testing library for the target language:

- Python: **Hypothesis**
- JavaScript/TypeScript: **fast-check**
- Haskell: **QuickCheck**
- Other languages: the established language-specific port of the same idea
  (e.g. `proptest` for Rust, `ScalaCheck` for Scala)

**Never invent a bespoke generate-and-check mechanism by hand.** A hand-rolled
loop of `for i in range(100): assert f(random_input())` is not a substitute
-- it lacks shrinking, doesn't explore the input space systematically, and
gives false confidence. If no real library exists for the target language,
that is a genuine `unknown` (unverifiable) result, not a reason to fake one
with bespoke code.

## What "real" requires

The property test must actually run and must exercise shrinking (the
library's built-in minimal-counterexample search) when it fails -- a
property test that never fails on any input in the session isn't evidence
of anything if it was never given a chance to fail. Where practical, verify
the harness works by first running it against a deliberately broken version
of the property (or checking the library's own self-test) before trusting a
clean pass.

## Verdict mapping

- Real library run, property holds across generated cases, no
  counterexample found -> `green`. Record the number of cases run.
- Real library run, counterexample found -> `red`. Record the shrunk
  counterexample verbatim (fenced, masked if it contains anything
  credential-shaped).
- No real property-testing library available for the target language ->
  `unknown`, with an explicit note that this is a tooling gap, not a claim
  the property was checked and failed. **Never fabricate confidence** by
  reporting `green` from an informal check when the real tooling was
  unavailable.

## Detection Ladder

Property tests are rung 2 (rendered-deterministic) by nature -- they execute
real code against generated inputs. There is no reason to climb higher for
this strategy; if the property concerns rendered UI output, that's a
separate wire better served by strategy a or a rung-3 check within it.

## Untrusted content and NO-PERSONA

Fence any generated counterexample before quoting it (it is derived from the
artifact under test and should be treated with the same caution). Justify
property choice by what the wire's contract actually states, never by "this
is the kind of property Bertrand Meyer would want."
