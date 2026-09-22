# Wire classifier

The decision procedure below is **executed**, not just described: it is
implemented verbatim as `route_wire()` in `scripts/andon_core.py` and invoked
via `andon_core.py route-wire`. This document explains *why* the order is
what it is, so you set the `signals`/`availability` flags correctly -- it is
not a second, competing decision procedure to reason through by hand.

## Check order and what each trigger means

1. **e -- structural claim** (`is_structural_claim`): the wire's contract is
   itself a claim about connectivity or structure -- "function X is called
   from module Y", "this import edge exists", "no cycle between these two
   packages". No hard prerequisite: `available_lsp_or_index` (a real
   Kythe/SCIP/LSIF index, or an LSP tool that can query one) only unlocks
   Tier 1. Checked first because a real index query is the strongest evidence
   class available and should never be skipped in favor of a weaker strategy
   when it applies.

2. **b -- numerical** (`is_numerical`): the wire produces a number without a
   known correct answer to compare against (a solver, an optimizer, a
   statistical fit). No external prerequisite -- oracle-gap V&V techniques
   are self-contained.

3. **f -- property/invariant** (`is_property_invariant`): the wire's contract
   is naturally expressed as "for all inputs matching X, Y holds" rather than
   a single example. Prerequisite: `available_property_lib` (Hypothesis,
   fast-check, or an equivalent already in the repo's dependencies).

4. **g -- verify-the-verifier** (`is_verifier_of_verifier`): the wire under
   test is itself a test, a check, or a verification harness -- the question
   is whether *it* would catch a real defect, not whether the code under it
   is correct. No external prerequisite.

5. **d -- agentic-reliability** (`is_autonomous_reliability`): the wire's
   contract concerns the reliability of an autonomous-fix loop itself
   (retry bounds, escalation paths, tool scope) rather than the fix's
   output. Prerequisite: `available_zeugnis` (the `zeugnis` plugin's
   `zeugnis-agentic-reliability` skill).

6. **c -- epistemic rubric** (`is_epistemic_claim`): the wire's contract is a
   claim about the world rather than about code -- a documented assumption,
   a design rationale, a "this is faster because..." justification. No
   external prerequisite.

7. **a -- tribunal** (fallback, no trigger flag): reached only when none of
   the above six triggers fired. This is the default for ordinary code
   changes: a Defender/Challenger/Verifier/Adjudicator duel over the diff.
   No external prerequisite -- this is why it is the safe universal floor
   for graceful degradation, never a starting assumption.

## Graceful degradation (tie-breaking on missing prerequisites)

If the trigger-selected strategy's prerequisite is unavailable, `route_wire()`
continues down the order from that strategy and lands on the next one whose
**own trigger also fired** and whose prerequisite is satisfied (or absent).
If no later strategy's trigger fired, it lands on `a`. Because `a` has no
trigger and no prerequisite, this walk always terminates in a usable
strategy -- `andon-verify` never hard-fails a wire's proof attempt for lack
of tooling; it reports the degraded strategy name (`degraded_from`) in the
evidence doc instead.

The trigger re-check is the point. A strategy's reference doc assumes the
wire has that strategy's shape: `b` demands a numeric quantity and a
significant-digit count, which a property wire missing its property library
cannot supply. Degrading onto a strategy whose trigger is false produces a
proof attempt that cannot be carried out, not a weaker one. So a property
wire without a property library (`f`) and an agentic-reliability wire
without `zeugnis` (`d`) both degrade to `a`, unless a later trigger fired too.

Strategy `e` is the exception: it never degrades to another strategy.
Without `available_lsp_or_index` it still runs, at Tier 2 (AST/grep static
analysis, see `structural-graph-tiers.md`), and `route_wire()` reports
`tier_ceiling: 2`. With an index it reports `tier_ceiling: 1`. An evidence doc
records that ceiling, and `validate-doc` refuses one missing it or recording a
tier above it (`SCHEMA_TIER_ABOVE_CEILING`) -- a Tier 1 label
is what makes a contradiction non-overridable, and without an index there was
no Tier 1 query to be non-overridable about.

## What NOT to do

- Do not pick strategy `a` because it "seems simplest" -- if `e` or `b`'s
  trigger is true and its prerequisite is available, use it; tribunal is a
  fallback, not a preference.
- Do not invent an eighth strategy for a wire that doesn't fit cleanly --
  pick whichever of the seven triggers is *closest*, and note the imperfect
  fit in the evidence doc's body rather than routing around the classifier.
