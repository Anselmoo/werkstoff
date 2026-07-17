---
name: react-factual-query
description: >-
  Answers a factual question using ReAct (Reason + Act) with a search tool.
  Use when the answer requires external lookup and the model cannot reliably
  answer from training data alone (recent events, specific statistics).
---

You are a research assistant with access to a web search tool.

Answer the question below using the ReAct format. Do not guess or hallucinate
— if you need a fact, look it up.

Available tools:
- `search(query: str)` — returns a list of web search result snippets

Format each step as:
```
Thought: <what you need to find out and why>
Action: search("<your search query>")
Observation: <result returned by the tool>
```

Repeat as needed. When you have enough information, end with:
```
Thought: I now have enough information to answer.
Final Answer: <your answer in 1-3 sentences, citing which search results you used>
```

Question: {{QUESTION}}

## Example trace

**Question:** What is the current population of Tokyo?

```
Thought: I need the current population of Tokyo. This changes year to year so I should search.
Action: search("Tokyo population 2025")
Observation: According to the Tokyo Metropolitan Government, Tokyo's population as of January 2025 is approximately 13.96 million in the city proper.

Thought: I have a recent, specific figure. I can answer.
Final Answer: Tokyo's population is approximately 13.96 million as of January 2025 (Tokyo Metropolitan Government).
```

## Why this technique

The question requires a current figure that may not be in Claude's training data. ReAct forces an explicit retrieval step rather than a confident hallucination, and the Thought-Action-Observation trace makes the reasoning auditable.

## When to escalate

If answering requires more than 5-6 search-observe cycles → break the question into sub-questions and use DSP (Technique 14) to structure the multi-hop retrieval. If no search tool is available → switch to RAG (Technique 10) with a pre-built document index.
