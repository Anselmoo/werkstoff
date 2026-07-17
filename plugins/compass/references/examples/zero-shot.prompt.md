---
name: zero-shot-legal-clause
description: >-
  Summarizes a legal clause in plain language using a zero-shot prompt.
  Use when you need to extract the key obligation, right, or risk from
  a contract clause without providing examples.
---

You are a plain-language contract analyst.

Read the clause below and produce a one-paragraph summary (3-5 sentences) for a non-lawyer. Cover:
1. What obligation or right the clause creates
2. Who it applies to (which party)
3. Any key condition, limitation, or deadline
4. The practical consequence if the clause is violated or not met

Do not use legal jargon. If a term is unavoidably technical, define it in parentheses.

<clause>
{{CLAUSE_TEXT}}
</clause>

## Why this technique

The task is well-defined (summarize → plain language → fixed output structure) and falls squarely within Claude's pre-training. Zero-shot works here because the output format is fully specified and the domain is common.

## When to escalate

If Claude misses key nuances (e.g., carve-outs, cross-references to other clauses) → add 2-3 few-shot examples of clause → summary pairs that demonstrate how to handle edge cases.

## Eval scenarios

- **Happy path**: Provide a typical input and verify the output matches the expected format.
- **Edge case**: Provide an ambiguous or empty input and verify graceful handling.
