---
task: "Collapse duplication hand-synced across N sites"
category: change-existing-code
summary: "Enumerate every copy exhaustively before deleting any of them — N-1 of N collapsed copies is worse than none."
openingPrompt: "There are multiple hand-synced copies of this file -- find every single one and everything that references them before deleting anything, pin down the shared behavior they all carry with tests while every copy still exists, and prove afterward that every consumer of the old copies still behaves the same, not just that the imports still resolve."
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
dos:
  - "Enumerate every copy and everything that references any of them, exhaustively, before deleting the first one."
  - "Write tests that pin the shared behavior while all the copies still exist -- the shared contract stops being observable once they're gone."
  - "Check for contract drift after consolidation -- which signature becomes authoritative can change silently."
  - "Prove every consumer still gets the same behavior with andon-verify -- a green import is not evidence for that."
donts:
  - "Don't collapse copies before the enumeration is exhaustive -- N-1 of N collapsed is worse than none, because the drift becomes invisible."
  - "Don't wait until after consolidation to pin the shared behavior down -- it's only observable while every copy still exists."
  - "Don't trust a green import as proof that every consumer still works -- that's the exact claim andon-verify has to prove instead of assume."
---

<RecipeHeader />

N byte-identical copies kept in step by hand is a defect with a countdown. The trap is
that collapsing them looks trivial, and the risk lives entirely in the sites that were
about to diverge.

<RecipeBeats />
