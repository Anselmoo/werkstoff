---
name: prompt-chaining-research-to-draft
description: >-
  Three-stage prompt chain: research extraction → outline → final draft.
  Use when producing a long-form document where quality of each stage
  can be independently verified before passing output to the next stage.
---

This is a three-stage chain. Run each prompt in order. Inspect the output
before proceeding to the next stage.

---

## Stage 1 — Extract key facts

You are a research analyst. Read the source material below and extract
all facts relevant to the writing topic.

Output format: a numbered list of facts, one per line.
Include: statistics, named entities, dates, key claims, and causal relationships.
Exclude: opinions, filler text, and facts unrelated to the topic.

Topic: {{TOPIC}}

<source_material>
{{SOURCE_TEXT}}
</source_material>

---

## Stage 2 — Build an outline (takes Stage 1 output)

You are an editor. Using only the facts listed below, create a structured
outline for a 600-word article on: {{TOPIC}}

The outline must have:
- A working title
- 3-5 sections with H2 headers
- 2-3 bullet points per section, each mapped to a specific fact number

<facts>
{{STAGE_1_OUTPUT}}
</facts>

---

## Stage 3 — Write the draft (takes Stage 2 output)

You are a writer. Write a 600-word article following the outline below.

Rules:
- Do not introduce facts not present in the outline.
- Each section must use the facts assigned to it.
- Use an active voice and professional but accessible tone.
- End with a one-sentence takeaway.

<outline>
{{STAGE_2_OUTPUT}}
</outline>

## Why this technique

Each stage produces an independently verifiable artifact (facts list → outline → draft). Errors caught at Stage 1 (wrong facts) or Stage 2 (bad structure) are cheap to fix and don't cascade into a full rewrite.

## When to escalate

If source material is very long (>10,000 tokens) → add a Stage 0 that chunks and summarizes the source before extraction. If the final draft requires a specific brand voice → add a Stage 4 revision pass with brand guidelines.

## Eval scenarios

- **Happy path**: Provide a typical input and verify the output matches the expected format.
- **Edge case**: Provide an ambiguous or empty input and verify graceful handling.
