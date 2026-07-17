---
name: ape-classifier-prompt-selection
description: >-
  Uses APE (Automatic Prompt Engineer) to generate five candidate prompts
  for a text classifier, score them against test cases, and select the best.
  Use when you need an optimized prompt for a classification task.
---

You are a prompt optimization engineer.

## Task

Generate and evaluate five candidate prompts for the following classifier:

**Classification task:** {{TASK_DESCRIPTION}}
**Labels:** {{LABEL_LIST}}
**Success criterion:** Highest accuracy on the test cases below.

---

## Step 1 — Generate 5 candidate prompts

Write five distinct prompts (labelled P1-P5) for this task. Each should:
- Give the model a clear role
- State the labels explicitly
- Specify the output format (respond with only the label)
- Take a different framing (e.g., rule-based, example-based, definition-based, question-based, chain-of-thought-based)

P1: [rule-based framing]

P2: [example-based framing]

P3: [definition-based framing]

P4: [question-based framing]

P5: [chain-of-thought framing]

---

## Step 2 — Score each prompt on test cases

For each test case, predict which label each prompt would produce.

**Test cases:**
1. "{{TEST_CASE_1}}" → Expected: {{LABEL_1}}
2. "{{TEST_CASE_2}}" → Expected: {{LABEL_2}}
3. "{{TEST_CASE_3}}" → Expected: {{LABEL_3}}
4. "{{TEST_CASE_4}}" → Expected: {{LABEL_4}}
5. "{{TEST_CASE_5}}" → Expected: {{LABEL_5}}

| Test | P1 | P2 | P3 | P4 | P5 |
|------|----|----|----|----|-----|
| TC1 | | | | | |
| TC2 | | | | | |
| TC3 | | | | | |
| TC4 | | | | | |
| TC5 | | | | | |
| **Score** | /5 | /5 | /5 | /5 | /5 |

---

## Step 3 — Select and explain

**Best prompt:** ___

**Score:** ___ / 5

**Why it outperforms the others:**

**Final recommended prompt:**

```
[paste the winning prompt here, cleaned up for production use]
```

## Why this technique

Classifier prompts are sensitive to framing. APE automates the otherwise manual process of writing, testing, and comparing variants. Scoring against labeled test cases makes the selection objective rather than subjective.

## When to escalate

If no prompt reaches 4/5 → the task may require few-shot examples (Rung 2) or the label definitions need to be revised. If test cases are ambiguous → add a Step 0 to clarify label boundaries before generating prompts.
