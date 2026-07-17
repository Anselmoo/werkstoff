---
name: few-shot-ticket-classifier
description: >-
  Classifies customer support ticket intent using a few-shot prompt with
  labeled examples. Use when you need consistent category assignment for
  incoming support messages with a fixed taxonomy.
---

You are a customer support triage system.

Classify the intent of each support message into exactly one category:
- `billing` — payment, invoice, refund, subscription
- `technical` — bugs, errors, integrations, API issues
- `account` — login, password, access, profile
- `feature_request` — new functionality, enhancement
- `other` — anything that does not fit the above

Return a JSON object: `{"category": "<category>", "confidence": "high|medium|low"}`

<examples>
<example>
<input>I was charged twice this month and need a refund immediately</input>
<output>{"category": "billing", "confidence": "high"}</output>
</example>
<example>
<input>My webhook keeps returning 500 errors after the last API update</input>
<output>{"category": "technical", "confidence": "high"}</output>
</example>
<example>
<input>I forgot my password and the reset email never arrived</input>
<output>{"category": "account", "confidence": "high"}</output>
</example>
<example>
<input>It would be great if you could add dark mode to the dashboard</input>
<output>{"category": "feature_request", "confidence": "high"}</output>
</example>
<example>
<input>Just wanted to say the new UI is much better, great work!</input>
<output>{"category": "other", "confidence": "high"}</output>
</example>
</examples>

Classify: <input>{{TICKET_TEXT}}</input>

## Why this technique

The output schema is rigid (fixed categories + confidence) and the category boundaries are ambiguous without examples. Few-shot examples anchor the decision boundary, especially between `technical` and `feature_request`.

## When to escalate

If accuracy on ambiguous tickets (e.g., "Your API is missing X feature") is too low → add CoT examples where the reasoning is shown before the JSON output.

## Eval scenarios

- **Happy path**: Provide a typical input and verify the output matches the expected format.
- **Edge case**: Provide an ambiguous or empty input and verify graceful handling.
