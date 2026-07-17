---
name: cot-word-problem
description: >-
  Solves a multi-step arithmetic word problem using chain-of-thought reasoning.
  Use when the answer requires several dependent calculations and you want
  Claude to show its work to reduce arithmetic errors.
---

You are a math tutor. Solve the following word problem step by step.

Rules:
- Write out every calculation — do not skip steps.
- Label each step clearly (Step 1, Step 2, …).
- At the end, state the final answer in a sentence beginning with "The answer is:".

<problem>
{{PROBLEM_TEXT}}
</problem>

## Example problem and solution

**Problem:** A store sells apples for $0.75 each and oranges for $1.20 each. Maria buys 8 apples and 5 oranges. She pays with a $20 bill. How much change does she receive?

**Solution:**
Step 1 — Cost of apples: 8 × $0.75 = $6.00
Step 2 — Cost of oranges: 5 × $1.20 = $6.00
Step 3 — Total cost: $6.00 + $6.00 = $12.00
Step 4 — Change: $20.00 − $12.00 = $8.00

The answer is: Maria receives $8.00 in change.

## Why this technique

Multi-step arithmetic requires intermediate values. Zero-shot often produces the right setup but wrong arithmetic on intermediate steps. Requiring explicit step labels forces Claude to compute each sub-result, making errors visible and correctable.

## When to escalate

If the problem involves many variables or conditional logic → use PAL (generate Python code and execute it) for guaranteed arithmetic correctness. If the problem requires external data (exchange rates, prices) → combine with RAG.
