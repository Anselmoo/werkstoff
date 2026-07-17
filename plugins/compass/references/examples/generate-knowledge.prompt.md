---
name: generate-knowledge-science-question
description: >-
  Answers a science question by first generating relevant background facts,
  then using only those facts to construct the answer. Use when Claude may
  not surface the right prior knowledge without explicit priming.
---

You are a science educator.

## Step 1 — Generate relevant knowledge

Before answering, list 6 key facts about the topic below that are directly
relevant to the question. Be specific: include quantities, mechanisms, and
named phenomena where relevant. Mark any fact you are less than 90% confident
about with ⚠️.

Topic: {{TOPIC}}
Question: {{QUESTION}}

Facts:
1.
2.
3.
4.
5.
6.

---

## Step 2 — Answer using those facts

Using only the facts you listed above (reference them by number), answer the question
in 3-5 sentences at a level appropriate for a first-year university student.

If a ⚠️ fact was necessary for your answer, state explicitly that the answer
relies on an uncertain premise.

---

## Example

**Question:** Why does ice float on water?

**Facts generated:**
1. Water molecules form hydrogen bonds.
2. In liquid water, hydrogen bonds are transient and allow molecules to pack ~15% more closely than in ice.
3. Ice has a crystalline lattice structure where each molecule is bonded to 4 others in a tetrahedral arrangement.
4. Density = mass / volume. Less dense objects float on denser ones.
5. Ice density ≈ 917 kg/m³; liquid water density ≈ 997 kg/m³ at 25°C.
6. The expansion of water upon freezing is about 9% by volume.

**Answer:** Ice floats on water because it is less dense than liquid water (Fact 5). When water freezes, its molecules arrange into a rigid crystalline lattice (Fact 3) that is more spread out than the transient packing in liquid water (Facts 2 & 6). This lower density (Fact 4) means ice displaces more water per unit mass, causing it to float.

## Why this technique

The "generate facts first" step forces Claude to surface relevant knowledge before reasoning, which reduces the chance of the answer being built on an omitted or misremembered premise. The ⚠️ flag makes uncertainty explicit.

## When to escalate

If ⚠️ flags appear on facts critical to the answer → switch to RAG (Technique 10) to inject verified facts from a trusted source before answering.
