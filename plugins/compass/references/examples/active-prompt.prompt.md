---
name: active-prompt-uncertainty-selection
description: >-
  Selects the most informative few-shot examples for a classification task
  by identifying which inputs the model is least confident about and using
  those as the examples. Use when you have a label pool and want to maximize
  example efficiency.
---

You are a data annotation advisor. Your goal is to select the most informative
labeled examples to include in a few-shot prompt.

## Context

**Task:** {{TASK_DESCRIPTION}}
**Candidate example pool:** {{CANDIDATE_POOL_SIZE}} unlabeled inputs
**Budget:** Choose {{EXAMPLE_BUDGET}} examples to label (labels are expensive)

---

## Step 1 — Zero-shot pre-screening

For each candidate input below, predict the label AND provide a confidence
score from 0-100 (100 = completely certain).

Output format:
| # | Input | Predicted label | Confidence |
|---|-------|----------------|------------|

Candidate inputs:
{{CANDIDATE_INPUTS}}

---

## Step 2 — Rank by uncertainty

Sort the candidates by confidence score (ascending). The lowest-confidence
inputs are the most informative examples to label.

**Most uncertain inputs (select top {{EXAMPLE_BUDGET}}):**
| Rank | # | Input | Confidence | Why it's ambiguous |
|------|---|-------|------------|-------------------|

---

## Step 3 — Construct the few-shot prompt

Using the selected inputs (assume they have been labeled by a human expert):
- Write the few-shot prompt incorporating these examples
- Explain why these examples are more useful than a random selection

**Few-shot prompt:**

```
{{TASK_INSTRUCTION}}

Examples:
[Example 1] Input: ... → Label: ...
[Example N] Input: ... → Label: ...

Now classify:
Input: {{NEW_INPUT}}
Label:
```

**Why these examples are better than random:**

## Why this technique

Random example selection often picks easy, redundant cases. Uncertainty-based selection — choosing inputs the model finds hardest — provides maximum information about the decision boundary, improving generalization with fewer labeled examples.

## When to escalate

If many inputs cluster in the same uncertainty zone → add diversity filtering (select examples that are both uncertain AND dissimilar to each other). If model confidence is uniformly low → the task definition may be unclear; clarify labels before selecting examples.

## Eval scenarios

- **Happy path**: Provide a typical input and verify the output matches the expected format.
- **Edge case**: Provide an ambiguous or empty input and verify graceful handling.
