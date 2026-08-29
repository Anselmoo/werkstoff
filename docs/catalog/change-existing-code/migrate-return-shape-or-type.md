---
task: "Migrate a return shape or type representation"
category: change-existing-code
summary: "Judge the new type's design and find every call site before rolling out a changed return shape."
external: ["claude-plugins-official"]
beats:
  - skill: "pr-review-toolkit:type-design-analyzer"
    why: "Rates encapsulation, invariant expression, and enforcement — cheapest before N call sites adopt the shape."
    prompt: "before we roll this new return type out everywhere, review its design — encapsulation, invariants, whether it's actually enforceable"
  - skill: "compass:compass-map-relationships"
    why: "An untyped or dynamically-dispatched call site is invisible to tooling and visible to an index."
    prompt: "find every call site that consumes this return value, including the dynamically-dispatched ones"
  - skill: "confab:confab-contract-drift"
    why: "Type hints, signatures, docstring params, and schemas drift apart precisely during this migration."
    prompt: "after the migration, check for drift between the declared signatures and how they're actually called"
  - skill: "andon:andon-verify"
    why: "Equivalence is the contract; a passing suite is evidence only if the suite would notice."
grounding: "the `core.py` to `cli.py` boundary in `tools/werkstoff-cli/src/werkstoff/`, whose output shape is pinned by the snapshot file `tools/werkstoff-cli/tests/__snapshots__/test_cli.ambr` — snapshots that will re-record silently if the migration lands before they are read."
---

Changing what a function hands back is a contract change wearing a refactor's clothes.
Every call site is a participant, and the compiler catches only the subset that is typed.
