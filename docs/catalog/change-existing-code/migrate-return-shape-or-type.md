---
task: "Migrate a return shape or type representation"
category: change-existing-code
summary: "Judge the new type's design and find every call site before rolling out a changed return shape."
openingPrompt: "We're changing what this function returns everywhere it's called -- review the new type's design before it rolls out to every site, track down every call site including the dynamic ones, and don't call the migration done until you've proven the old and new behavior are actually equivalent, not just that the suite is green."
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
dos:
  - "Review the new return type's design -- encapsulation, invariants, enforceability -- before any call site adopts it; it's cheapest to fix now, before N sites depend on the shape."
  - "Enumerate every call site the return value reaches, including the dynamically-dispatched ones an index catches and a type-checker alone would miss."
  - "Prove equivalence with andon-verify once the migration lands -- a passing suite counts as evidence only if the suite would actually notice a regression."
donts:
  - "Don't skip contract-drift checking after the rollout -- signatures, docstring params, and schemas drift apart precisely during this kind of migration."
  - "Don't trust a green test suite as proof the old and new shapes behave the same -- check whether it would actually catch the difference."
  - "Don't let the migration land before snapshot tests like `tests/__snapshots__/test_cli.ambr` are read -- they re-record silently and swallow the exact drift this recipe exists to catch."
---

<RecipeHeader />

Changing what a function hands back is a contract change wearing a refactor's clothes.
Every call site is a participant, and the compiler catches only the subset that is typed.

<RecipeBeats />
