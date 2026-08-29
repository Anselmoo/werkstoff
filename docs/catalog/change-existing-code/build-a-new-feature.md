---
task: "Build a new feature in an existing codebase"
category: change-existing-code
summary: "Explore before designing, design before building, and stay skeptical of the design once it exists — the ordering that keeps the most common development task from becoming ad hoc."
external: ["superpowers", "claude-plugins-official"]
beats:
  - skill: "feature-dev:code-explorer"
    why: "Traces execution paths and maps layers while the design is still negotiable; its tools grant has no Write/Edit, so it cannot drift into building before the design is settled."
    prompt: "before we design anything, trace how the existing code around this feature actually works — layers, data flow, the abstractions already in play"
  - skill: "feature-dev:code-architect"
    why: "Produces the blueprint naming specific files to create/modify and the build sequence — a blueprint written after the first file exists is a rationalization, not a plan."
    prompt: "now give me a concrete blueprint: which files to create or modify, the component design, and the order to build them in"
  - skill: "code-modernization:architecture-critic"
    why: "Its default stance is skeptical — looks for over-engineering and simpler alternatives. Cheapest to apply against a blueprint, worthless once the branch is already built."
    prompt: "review this blueprint adversarially before I start — where is this over-engineered, and what's the simpler alternative?"
  - skill: "superpowers:test-driven-development"
    why: "Tests written after the feature exists test the feature that got built, not the one that was specified."
  - skill: "andon:andon-verify"
    why: "The new feature's integration with existing stages is a wire, not a formality; a green test suite is not by itself evidence that wire holds."
grounding: "Adding a subcommand to tools/werkstoff-cli/src/werkstoff/ — cli.py and core.py split the surface, and tests/__snapshots__/test_cli.ambr will re-record silently if the feature lands before the snapshot is read, which is exactly the kind of integration wire andon-verify exists to check rather than assume."
---

Building a new feature is the most common development task, and the easiest to let
slide into ad hoc work. `feature-dev:code-explorer` and `feature-dev:code-architect`
keep exploration and design as separate, sequential steps; `code-modernization:architecture-critic`
is cheapest to apply against a blueprint that has not yet become a branch. Tests come
from superpowers' test-driven-development before the feature exists to test, and
`andon:andon-verify` checks the new feature's integration with existing stages as a wire,
not a formality.
