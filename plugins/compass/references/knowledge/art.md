---
type: prompting-technique
title: Automatic Reasoning and Tool-use (ART)
description: Dynamically select tools from a library at each step, calling only what's genuinely needed, when the task flow can't be predetermined.
resource: ../examples/art.prompt.md
tags: [compass-investigate-dynamically]
timestamp: 2026-07-15T00:00:00Z
---

# ART — Automatic Reasoning and Tool-use

For open-ended multi-step tasks where a fixed tool sequence would fail
because each step's result determines the next action: select tools
from an available library at each step, calling only what's genuinely
needed for the next step, never speculatively.

## Mechanism

`Reasoning:` (why this tool, now) / `Tool call:` / `Result:` per step,
repeated dynamically, ending in a `Final output:` — the tool sequence
is discovered, not planned upfront.

## When to apply

- Each step's result determines the next action — a fixed sequence
  would fail
- Open-ended multi-step research or investigation

## Examples

### In `../examples/art.prompt.md`

Comparing two 2024 JS frameworks: `search` to find candidates,
`fetch_url` per candidate, `compare` once enough detail exists — each
call's necessity only became clear after the prior call's result.

### In werkstoff

This session's own parallel-subagent dispatch decisions are ART in
spirit: whether to spawn a background `Agent` call, use `WebSearch`, or
read a file directly was decided per-step based on what the *previous*
step's result actually revealed (e.g. discovering `techniques.json`'s
real shape before deciding how to model `compass`'s own registry, or
discovering the deep-research Workflow's synthesis bug before deciding
to fetch sources manually instead). `compass-investigate-dynamically`
is ART's (and ReAct's) shared dedicated skill.
