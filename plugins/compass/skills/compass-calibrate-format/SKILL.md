---
name: compass-calibrate-format
description: This skill should be used when the user asks to "match this format", "make it look like these", "I don't know how to describe the output I want", "here's what good output looks like", "keep the same style as before", or when a task's desired output format, style, tone, or schema is ambiguous, non-standard, or hard to pin down in words — a fixed taxonomy with fuzzy category boundaries, an idiosyncratic house style, a schema no public spec documents, or any case where prose description keeps under- or over-specifying the target shape.
---

Anchor an ambiguous or non-standard output format on 2-5 concrete
input/output examples instead of a prose description of the format. This
is the few-shot technique, generalized from
`few-shot.prompt.md`'s exact `<examples>` mechanism:
examples fix a decision boundary that adjectives ("professional",
"concise", "the usual format") cannot — a category boundary like
`technical` vs. `feature_request` is not something prose reliably pins
down, but a labeled example pair is unambiguous.

## When to use

- The desired output has a fixed but fuzzy-boundaried schema (categories,
  fields, a specific structure) and prose keeps drifting or leaving edge
  cases undefined.
- The user says something closer to "make it look like this" than "here
  is the spec for this."
- A prior attempt at this task produced output the user rejected as
  "not quite right" without being able to say exactly what rule it
  violated — a signal the rule lives in examples, not words.

**Do not use** when the format is already a well-documented public
schema (OpenAPI, a language's AST, a standard file format) — read the
spec instead of reverse-engineering it from examples. Do not use for
reasoning-quality problems (wrong answer, not wrong shape) —
`compass-reason-verify` covers that.

## Step 1 — Source the examples: prior outputs first, constructed only as fallback

Before writing a single example, check whether the user already has real
prior outputs in this shape — a repo of past deliverables, a chat history
of accepted responses, existing files matching the target format. Ask
directly if unclear: "Do you have 2-5 examples of output you've already
approved in this format?" Real prior outputs are strictly preferred over
constructed ones — they carry the user's actual, unstated conventions
that a constructed example can only guess at.

Only construct examples when no real prior output exists. Constructed
examples must be built to the same bar the source template sets in its
own eval-scenario discipline: cover a **happy path** and at least one
**edge case** per example set, and deliberately include an example that
sits near the boundary between two plausible interpretations of the
format (the ticket classifier's `technical` vs. `feature_request`
example pair is the model: two inputs close enough that a prose rule
would blur them, resolved unambiguously by the labeled pair).

**Do not stop at trivial or toy demonstrations.** A set of 2-5 examples
that all look alike (same length, same complexity, no edge case, no
near-boundary pair) fixes nothing — it just restates the easy case five
times and leaves the actual ambiguity unresolved. If every example in
the set would obviously produce the same output under either candidate
interpretation of the format, the set has not done its job; replace at
least one with a case that only makes sense under the intended
interpretation.

## Step 2 — Build the `<examples>` block

Structure the block exactly as `few-shot.prompt.md`
does — this exact nesting, not a paraphrase of it:

```xml
<examples>
<example>
<input>...</input>
<output>...</output>
</example>
<example>
<input>...</input>
<output>...</output>
</example>
</examples>
```

2-5 examples total (fewer than 2 is not few-shot; more than 5 usually
means the examples are compensating for a format that still isn't
pinned down, or is pulling in near-duplicate cases that add tokens
without adding signal — per this plugin's context-rot constraint, see
below). Each `<input>`/`<output>` pair should be complete and realistic,
not truncated or abstracted — a partial example teaches a partial rule.

## Step 3 — State the task around the examples, not instead of them

Keep the prose description minimal and let the examples carry the actual
decision boundary, mirroring the source template's own structure: a
short task statement, any hard constraints that apply uniformly (e.g. a
fixed field list or output-wrapper format), then the `<examples>` block,
then the real input to process. Do not let the prose re-explain what the
examples already show — a long prose restatement on top of the examples
is redundant at best and contradictory at worst if the two drift out of
sync.

## Common mistakes

| Mistake | Fix |
|---|---|
| Constructing examples when real prior outputs exist | Ask for and use the user's own prior outputs first |
| All examples share one shape (same length/complexity, no edge case) | Replace at least one with a genuine edge case or near-boundary pair |
| Prose description repeats or contradicts the examples | Trim prose to constraints the examples don't already show |
| Fewer than 2 or more than 5 examples | Stay in the 2-5 range; more usually signals an unresolved ambiguity, not more calibration |
| Examples given but the real input is compared against them only informally | Reference the examples explicitly as the decision boundary when producing the final output |

## Escalating beyond few-shot

If accuracy on ambiguous or near-boundary inputs stays low even with a
well-built example set — the source template's own named escalation
signal — add chain-of-thought to each example: show the reasoning that
leads to the labeled output, not just the output itself, before falling
back to a different technique. This escalation is `compass-reason-verify`'s
territory (its CoT tier), not a re-attempt within this skill.

Source technique (vendored locally, no external repo dependency):
`../../references/knowledge/few-shot.md` — see `../../references/knowledge/index.md`.

For the context-rot and plausible-vs-verified constraints that apply to
example selection and every other `compass-*` skill, see
`../../references/constraints.md`.
