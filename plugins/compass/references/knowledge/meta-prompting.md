---
type: prompting-technique
title: Meta-Prompting
description: Generate a prompt, critique it against an explicit checklist, then revise — bootstrapping a considered first draft.
resource: ../examples/meta-prompting.prompt.md
tags: [compass-optimize-instruction]
timestamp: 2026-07-15T00:00:00Z
---

# Meta-Prompting

For bootstrapping a new prompt/instruction where the right framing
isn't obvious: generate a draft, critique it against an explicit
checklist (are behavioral rules unambiguous? does it handle
out-of-scope requests? are output-format rules mutually compatible? is
anything two-ways interpretable?), revise only what failed a criterion.

## Mechanism

Generate → checklist critique (✓/✗ + 1-sentence reason per item) →
revise only the failed sections, output the final revised prompt only.

## When to apply

- Bootstrapping a new prompt where the framing isn't yet obvious
- Sharpening an already-selected candidate (e.g. after APE) further

## Examples

### In `../examples/meta-prompting.prompt.md`

A coding-assistant system prompt generated, then checked against a
4-item ambiguity/scope/format-compatibility checklist, revised where it
failed.

### In werkstoff

This is, structurally, what `superpowers:writing-plans`'s own
"Self-Review" step does to the *plan document itself*: after drafting,
check for placeholder red flags, internal contradictions, scope
mismatches, and ambiguity — fix inline, no full rewrite — the same
generate-then-checklist-critique loop meta-prompting formalizes,
applied to a plan instead of a prompt. `compass-optimize-instruction`'s
Critique phase applies meta-prompting's checklist to APE's winning
instruction candidate specifically (never all 5 candidates, only the
selected one).
