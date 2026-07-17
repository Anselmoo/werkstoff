# Cross-cutting constraints

Two constraints from the design spec's research grounding that every
`compass-*` skill inherits — referenced by path from each skill rather
than restated, so they stay in one place.

## Context rot: less, well-chosen context beats more

Accuracy on a long software-engineering benchmark fell from 29% to 3%
as context grew from 32K to 256K tokens (the "Spec Growth Engine"
paper's finding, surfaced during this repo's `quality`-plugin research).
Models use long contexts unevenly and retrieve worst from the middle —
adding more examples, more facts, more retrieved passages is not a
free precision upgrade, and past a point it actively degrades the
result.

**Applies to:**
- `compass-clarify-scope`'s `known_facts` — keep to what's genuinely
  load-bearing for the task, not an exhaustive context dump.
- `compass-calibrate-format`'s example set — 2-5 diverse examples, not
  as many as can be found.
- `compass-ground-evidence`'s cited sources — cite what's actually used,
  not everything retrieved "to be thorough."
- `compass-map-relationships`'s triple table — the relevant subgraph for
  the question at hand, not the entire graph (the source template's own
  escalation note: pre-filter past ~50 triples).
- `compass-decompose-chain`'s stage input contracts — each stage should
  consume only what its own output contract actually requires from
  upstream, never "context from earlier" as a blanket allowance.

## Plausible-vs-verified: an output that looks right is not the same as one that is right

LLM-generated tests systematically achieve reasonable code coverage
while asserting little — they execute code without verifying behavior
(the mutation-testing research `quality-assertion-audit` is built on).
The same failure shape applies to prompts and reasoning generally: a
confident, well-formatted answer is not evidence it is correct.

**Applies to:**
- `compass-reason-verify` — a fluent Chain-of-Thought is not proof of a
  correct answer; the self-consistency and PAL escalation tiers exist
  specifically because a single plausible-sounding reasoning chain can
  still be wrong.
- `compass-draft-revise` — score against real, checkable criteria, never
  an impression of quality.
- `compass-ground-evidence` — this constraint is the skill's entire
  mandate: a claim is not verified because it sounds right, only
  because it is cited.
- `compass-optimize-instruction` — a candidate instruction that "looks
  like" it would pass a test case is not the same as one actually
  scored against it; this is why `optimize-instruction-scan.js` refuses
  to invent its own test cases and requires the caller's real ones.
- `compass-investigate-dynamically` — every claim in a Final output must
  trace back to an actual Observation in the trace, never a plausible
  fill-in for a gap the loop never actually resolved.
