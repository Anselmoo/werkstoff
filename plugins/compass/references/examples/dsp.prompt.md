---
name: dsp-multihop-question
description: >-
  Answers a multi-hop question using DSP (Demonstrate-Search-Predict):
  decompose into sub-questions, retrieve facts for each, then synthesize.
  Use when a question requires combining information from multiple separate
  sources that cannot be answered in a single retrieval step.
---

You are a research analyst using a structured multi-hop retrieval process.

## Question

{{MULTIHOP_QUESTION}}

---

## Step 1 — Decompose

Break the main question into 2-4 sub-questions that can each be answered
with a single fact or retrieval.

Sub-questions:
1.
2.
3.
(4. if needed)

---

## Step 2 — Retrieve facts for each sub-question

For each sub-question, provide the retrieved fact (from the documents below or your knowledge)
and its source.

| Sub-question | Fact | Source |
|-------------|------|--------|
| 1. | | |
| 2. | | |
| 3. | | |

<documents>
{{RETRIEVED_DOCUMENTS}}
</documents>

---

## Step 3 — Synthesize the final answer

Using only the facts retrieved in Step 2, answer the original question.
- Cite sub-question numbers to show how the answer was assembled.
- Do not introduce facts not retrieved in Step 2.

**Final answer:**

---

## Example

**Question:** Which country was the founder of the company that makes the most-used smartphone OS, and what is its current GDP?

**Sub-questions:**
1. What is the most-used smartphone OS?
2. Who founded the company that makes that OS?
3. What country is that founder from?
4. What is that country's current GDP?

**Facts:**
1. Android (71% market share globally as of 2024)
2. Android was developed at Android Inc., founded by Andy Rubin
3. Andy Rubin was born in the United States
4. US GDP: ~$28.8 trillion (2024 IMF estimate)

**Final answer:** Android is the most-used smartphone OS (Sub-Q 1). It was created by Andy Rubin (Sub-Q 2), who is American (Sub-Q 3). The United States' GDP is approximately $28.8 trillion (Sub-Q 4).

## Why this technique

Multi-hop questions fail with single-shot retrieval because the first retrieval depends on the answer to the second. DSP's explicit decompose-retrieve-synthesize pipeline makes each reasoning link auditable and replaceable if a retrieved fact is wrong.

## When to escalate

If sub-questions themselves require multi-hop retrieval → recursively apply DSP. If 4+ retrieval rounds are needed → consider using an ART agent (Technique 11) for fully dynamic tool orchestration.
