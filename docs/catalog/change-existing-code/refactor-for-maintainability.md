---
task: "Refactor for maintainability"
category: change-existing-code
summary: "Measure where the debt actually is and map real dependencies before pinning behavior and refactoring."
openingPrompt: "I want to refactor this for maintainability -- measure where the complexity and architecture debt actually is before touching anything, pin the current behavior down with tests first, and once the refactor is done, check for contract drift and have an independent pass confirm the module behaves identically to before, from the diff rather than from my own account of what changed."
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
dos:
  - "Measure complexity and size per module before refactoring -- targeting by intuition hits the code that's annoying, not the code that's costly."
  - "Check for god-modules, cycles, and layering violations before refactoring -- a refactor that ignores them relocates the problem instead of fixing it."
  - "Write characterization tests before the refactor, not after -- tests written after a refactor only characterize the refactor."
  - "Have equivalence checked post-hoc, from the diff itself, rather than trusting the refactorer's own report of what changed."
donts:
  - "Don't refactor by intuition -- it targets the annoying code, not the costly code."
  - "Don't ignore god-modules, cycles, or layering violations found in the architecture check -- a refactor around them just relocates the problem."
  - "Don't write the characterization tests after the refactor -- by then they characterize the refactor, not the original behavior."
  - "Don't rely on your own report that behavior is unchanged -- verify it independently from the diff and the module's own tests."
---

# Refactor for maintainability

Refactoring's defining constraint is that behavior must not change — which makes the
before-picture and the after-proof more important than the edit itself. Superpowers'
test-driven-development pins behavior first; `codebase-consistency:equivalence-verifier`
re-checks it afterward, genuinely post-hoc.
