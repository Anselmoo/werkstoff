# Strategy f — Property/invariant-based proof

For wires whose contract is expressible as an **invariant across an
input space**, not a single known-answer example. Distinct from strategy
b (numerical-correctness-specific — a solver's order of accuracy, a
fit's parameter recovery) and from strategy a (LLM judgment against a
rubric). This strategy generates inputs across the space using a real,
established property-based testing library and checks a stated invariant
holds — never a bespoke, invented property-testing mechanism.

## When this strategy fires

The wire's contract can be stated as "for all valid inputs X, property P
holds" — round-trip identities (serialize/deserialize), ordering
invariants (sort output is non-decreasing), algebraic laws (associativity,
idempotence), or structural invariants (output always satisfies schema
S) — where a handful of example-based tests would leave the space mostly
unchecked.

## Required real tooling per language — do not invent a substitute

| Language | Library | Notes |
|---|---|---|
| Python | **Hypothesis** | `pip install hypothesis`; strategies (`st.integers()`, `st.text()`, `st.builds(...)` for custom types) generate inputs, `@given` decorates the test. |
| JavaScript / TypeScript | **fast-check** | `npm install --save-dev fast-check`; `fc.assert(fc.property(fc.integer(), ...))`. |
| Haskell | **QuickCheck** | The originator of the property-based testing idea; `quickCheck (\x -> prop x)`. |
| Other languages | The QuickCheck-family port for that ecosystem (e.g. `proptest` for Rust, `ScalaCheck` for Scala, `Clojure.spec`/`test.check` for Clojure) | If no such library exists for a niche language, report that plainly — do not hand-roll a random-input generator as a silent substitute; the shrinking behavior (below) is the part a bespoke generator would not reliably reproduce. |

## Workflow

1. **State the invariant precisely** — a single sentence of the form "for
   all `<input space>`, `<property>` holds." If it can't be stated this
   way, this is the wrong strategy (route to a or b instead per
   `wire-classifier.md`).
2. **Write the property test** using the language's real library from the
   table above. Bound the input space realistically (the type/domain the
   wire's contract actually claims to accept) — an unbounded or
   nonsensical generator produces noise, not signal.
3. **Run it.** Let the library generate and check across many inputs
   (its own default iteration count is normally sufficient; do not
   silently reduce it to make a flaky property look green).
4. **On failure, let the library shrink** to a minimal counterexample —
   this is the whole point of using real tooling here rather than
   hand-written random inputs: Hypothesis/fast-check/QuickCheck all
   automatically reduce a failing case to the smallest input that still
   reproduces it (e.g. the zero-width-peak NaN nobody would think to
   hand-write). Report the shrunk counterexample verbatim in the evidence
   doc — never just "it failed on some input."

## Verdict → wire status

- Property holds across the library's generated run → 🟢. Note the
  library and iteration count in the evidence doc so the claim is
  reproducible, not just asserted.
- Property fails → 🔴, with the shrunk minimal counterexample as the
  evidence. This is a genuine wire-proof failure and triggers
  `andon-loop`'s stop rule condition 1 like any other strategy's red
  verdict.
- No real property-testing library exists for the target language and no
  reasonable port exists → ⚪, explicitly reported as "cannot verify this
  invariant with real tooling for this language" — never fabricate a
  substitute mechanism to force a verdict.

## Relationship to strategy b

If the invariant in question is really about numerical correctness
against a scientific/mathematical model (conservation laws, symmetry,
asymptotic limits), strategy b's metamorphic-relations technique is more
specific and should be preferred — it's the same underlying idea
(property that must hold without a known answer) but strategy b adds the
numerical-reliability layer (condition number, significant digits) that
this strategy does not cover. Use f for structural/logical invariants,
b for numerical ones.
