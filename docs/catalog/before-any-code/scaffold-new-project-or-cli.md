---
task: "Scaffold a new project or CLI"
category: before-any-code
summary: "Load the production-grade doctrine before generating a scaffold, since a scaffold that violates it is cheaper to regenerate than retrofit."
openingPrompt: "I want to scaffold a new CLI for this -- brainstorm what it should actually do before any code exists, load the production-grade architecture doctrine before the paradigm skill generates anything, and verify the result against the five pillars while it's still disposable enough to regenerate rather than patch."
external: ["superpowers"]
beats:
  - skill: "superpowers:brainstorming"
    why: "Required before any creative work; a scaffold generated from an unexamined idea encodes the idea's flaws structurally."
    prompt: "I want to build a small CLI for this. Let's brainstorm what it should do before any code exists."
  - skill: "cli-scaffold:cli-architecture"
    why: "Its own instruction: load \"BEFORE any paradigm skill ... generates a scaffold\"."
  - skill: "cli-scaffold:cli-scaffold-interpreted"
    why: "Paradigm choice (compiled / interpreted / shell) is fixed by language and cannot be swapped later without regenerating; loads the cli-architecture doctrine first."
    prompt: "scaffold a production-grade Python CLI for this, following the architecture doctrine rather than a bare template"
  - skill: "cli-scaffold:cli-scaffold-verifier"
    why: "Checks the five pillars and the frozen 0/1/2 exit-code contract while the scaffold is still disposable."
    prompt: "verify the scaffold you just generated against the five pillars — read-only, don't fix anything yet"
grounding: "`tools/werkstoff-cli/` is the shape a sibling CLI in this repo should match: a `src/werkstoff/` package split into `cli.py` and `core.py`, snapshot tests under `tests/__snapshots__/`, and a `pyproject.toml` pinning `requires-python = \">=3.12\"`."
dos:
  - "Brainstorm what the CLI should do before any code exists -- a scaffold generated from an unexamined idea encodes the idea's flaws structurally."
  - "Load the cli-architecture doctrine before the paradigm skill runs, every time -- it states this about itself."
  - "Verify the scaffold against the five pillars and the exit-code contract while it's still disposable, before anything is built on top of it."
donts:
  - "Don't pick a paradigm (compiled/interpreted/shell) expecting to swap it later -- it's fixed by language and cannot be swapped without regenerating."
  - "Don't let the paradigm skill generate a scaffold before the architecture doctrine has loaded -- retrofitting it afterward is more expensive than loading it first."
  - "Don't treat verification as optional once the scaffold exists -- it's cheapest to fix while still disposable."
---

# Scaffold a new project or CLI

Scaffolding is the one task where the doctrine must be loaded before the generator runs,
because a scaffold that violates the doctrine is cheaper to regenerate than to retrofit.
Paradigm choice — compiled, interpreted, or shell — is fixed by language and cannot be
swapped later without regenerating.
