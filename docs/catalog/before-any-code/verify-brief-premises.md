---
task: "Verify a brief's premises before acting"
category: before-any-code
summary: "Test a brief's load-bearing claims — where something lives, what a job does — before opening a single file to edit."
openingPrompt: "Before we open a single file to edit, list every load-bearing assumption this brief is resting on, confirm each one against a real file and line number, and check that any new dependencies it names actually exist on the registry."
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
dos:
  - "List the brief's assumptions and flag which ones can't actually be confirmed, before implementation starts."
  - "Ground every claim about the repo in a real file and line number -- cheap on five claims, expensive on a finished diff."
  - "Check that every newly named dependency actually exists on the registry before adding it."
donts:
  - "Don't start implementing on a premise that hasn't been checked -- a false premise discovered mid-implementation reads as a bug, not as the false claim it actually was."
  - "Don't assume a brief's claim about where something lives is unique just because it names one location -- this repo has had a brief collapse on exactly that assumption."
  - "Don't add a named dependency without confirming it exists -- a hallucinated or typosquat-adjacent package is free to catch now and expensive later."
---

<RecipeHeader />

Most bad work is correct work aimed at a premise that was never true. A brief arrives
asserting where something lives, what a job does, or which package is already a
dependency — and the cheapest possible moment to test those assertions is before a single
file is opened for editing.

<RecipeBeats />
