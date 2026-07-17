---
type: prompting-technique
title: ReAct
description: Interleave Thought/Action/Observation steps, looking things up rather than guessing, when external information is required.
resource: ../examples/react.prompt.md
tags: [compass-investigate-dynamically]
timestamp: 2026-07-15T00:00:00Z
---

# ReAct — Reason + Act

For answers requiring external or current information the model can't
reliably produce alone: interleave Thought (what's needed and why) →
Action (a tool call) → Observation (the result), repeating until enough
information exists, ending with a Final Answer that cites which
observations it used.

## Mechanism

Explicit `Thought:` / `Action: tool("...")` / `Observation:` blocks,
repeated as needed, ending in `Final Answer:` — never a confident
answer without a preceding lookup when the fact is genuinely uncertain
or time-sensitive.

## When to apply

- Answers requiring current or specific external facts
- Guessing risk is high without an explicit retrieval step

## Examples

### In `../examples/react.prompt.md`

"What is Tokyo's current population?" answered via one
Thought/Action(`search`)/Observation cycle rather than a confident
guess from training data.

### In werkstoff

**This entire conversation's own tool-use pattern is ReAct**: every
`Bash`/`WebFetch`/`Read` call in this session is preceded by an
implicit "I need X because Y" (Thought) and followed by acting on what
was actually returned (Observation), rather than assuming file
contents or search results in advance — visible concretely in this
session's earlier `curl` calls to GitHub's API to check code-modernization's
actual command count rather than guessing it. `compass-investigate-dynamically`
formalizes this as a named, explicit step format for any task with an
undiscoverable-upfront action sequence.
