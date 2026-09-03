---
task: "Verify a brief's premises before acting"
category: before-any-code
summary: "Test a brief's load-bearing claims — where something lives, what a job does — before opening a single file to edit."
external: []
beats:
  - skill: "compass:compass-verify-assumptions"
    why: "Once implementation starts, a false premise is discovered as a bug rather than as a claim."
    prompt: "before we do any of this, list the assumptions this request is resting on and tell me which ones you can't actually confirm"
  - skill: "compass:compass-ground-evidence"
    why: "Grounding is cheap on five claims and expensive on a finished diff."
    prompt: "don't make this up — every claim about this repo needs a file and line number behind it"
  - skill: "confab:confab-dependency-audit"
    why: "A hallucinated or typosquat-adjacent package name is free to catch now and a supply-chain incident later."
    prompt: "the plan names three new dependencies — check they actually exist on the registry before we add any of them"
grounding: "a brief asserting that the symbol indexer lives only in `tools/symbol-indexer/` collapses on the first grounding pass: five plugins each carry a byte-identical `scripts/build_symbol_index.py`."
---

<RecipeHeader />

Most bad work is correct work aimed at a premise that was never true. A brief arrives
asserting where something lives, what a job does, or which package is already a
dependency — and the cheapest possible moment to test those assertions is before a single
file is opened for editing.

<RecipeBeats />
