---
task: "Refactor for maintainability"
category: change-existing-code
summary: "Measure where the debt actually is and map real dependencies before pinning behavior and refactoring."
external: ["superpowers"]
beats:
  - skill: "self-assess:self-assess-complexity-score"
    why: "Refactoring by intuition targets the code that is annoying rather than the code that is costly."
    prompt: "measure complexity and size per module so we refactor where the debt actually is"
  - skill: "self-assess:self-assess-arch-health"
    why: "God-modules, cycles, and layering violations are structural findings; a refactor that ignores them relocates the problem."
    prompt: "check this repo's architecture health — god modules, cycles, layering violations, with evidence"
  - skill: "superpowers:test-driven-development"
    why: "Characterization tests written after the refactor characterize the refactor."
  - skill: "confab:confab-contract-drift"
    why: "Its own description scopes it to checking \"for contract drift after a refactor.\""
    prompt: "check for contract drift after this refactor — signatures, type hints, docstring params, schemas"
  - skill: "codebase-consistency:equivalence-verifier"
    why: "Genuinely post-hoc: it re-checks that the module behaves identically to before and that its docs and comments still match, from the diff rather than from the refactorer's own report."
grounding: "`tools/plugin-serializer/` holds four scripts — `build_inventory.py`, `contract_diff.py`, `extract_behavior.py`, `generate_plugin.py` — whose shared assumptions about plugin shape make it a real candidate for the measure-then-map-then-pin sequence above."
---

<RecipeHeader />

Refactoring's defining constraint is that behavior must not change — which makes the
before-picture and the after-proof more important than the edit itself. Superpowers'
test-driven-development pins behavior first; `codebase-consistency:equivalence-verifier`
re-checks it afterward, genuinely post-hoc.

<RecipeBeats />
