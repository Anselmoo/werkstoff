---
task: "Collapse duplication hand-synced across N sites"
category: change-existing-code
summary: "Enumerate every copy exhaustively before deleting any of them — N-1 of N collapsed copies is worse than none."
external: ["superpowers"]
beats:
  - skill: "compass:compass-map-relationships"
    why: "Collapsing N-1 of N copies is worse than collapsing none; the enumeration must be exhaustive before the first deletion."
    prompt: "find every copy of this file and every place that references any of them — I want the complete list before we delete anything"
  - skill: "superpowers:test-driven-development"
    why: "The shared contract is only observable while all copies still exist."
    prompt: "before we collapse these copies, write tests that pin the behavior all of them share"
  - skill: "confab:confab-contract-drift"
    why: "Consolidation silently changes which signature is authoritative."
  - skill: "andon:andon-verify"
    why: "\"All consumers still work\" is a contract, and a green import is not evidence for it."
    prompt: "prove the wire: after consolidation, every consumer of the old copies still gets the same behavior"
grounding: "five plugins each carry a `scripts/build_symbol_index.py` that is byte-identical to `tools/symbol-indexer/build_symbol_index.py` (all six share MD5 `1401d8e53d60aaffeab46c1d0cfc05b6`), and only the canonical copy has a test suite — `tools/symbol-indexer/test_build_symbol_index.py`, which is what `plugin-checks.yml` runs."
---

<RecipeHeader />

N byte-identical copies kept in step by hand is a defect with a countdown. The trap is
that collapsing them looks trivial, and the risk lives entirely in the sites that were
about to diverge.

<RecipeBeats />
