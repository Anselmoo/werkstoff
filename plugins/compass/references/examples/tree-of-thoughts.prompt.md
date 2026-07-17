---
name: tree-of-thoughts-strategic-planning
description: >-
  Generates and scores three strategic approaches to a planning problem,
  then selects the best branch and expands it into a concrete action plan.
  Use for decisions with multiple viable paths and meaningful tradeoffs.
---

You are a strategic advisor. Use Tree-of-Thoughts to solve the planning challenge below.

**Challenge:** {{PLANNING_CHALLENGE}}

---

## Phase 1 — Generate branches

Describe three distinct strategic approaches. Each must represent a genuinely
different direction — not variations of the same idea.

### Branch A: [Name]
Description (2-3 sentences):

### Branch B: [Name]
Description (2-3 sentences):

### Branch C: [Name]
Description (2-3 sentences):

---

## Phase 2 — Score each branch

For each branch, score 1-10 on three dimensions:

| Dimension | Branch A | Branch B | Branch C |
|-----------|---------|---------|---------|
| Feasibility (can we execute this?) | | | |
| Impact (how much does success move the needle?) | | | |
| Risk (lower = less risky) | | | |
| **Total** | | | |

Identify the biggest unknown or blocker for each branch (1 sentence each).

---

## Phase 3 — Select and expand

Select the highest-scoring branch. If two branches tie, choose the one with
the lower risk score.

**Selected branch:** ___

**Why this branch over the alternatives:** (2-3 sentences)

**First 5 concrete actions to execute this branch:**
1.
2.
3.
4.
5.

**Early warning signal:** What would indicate this branch is failing within 30 days?

---

## Example challenge

**Challenge:** A 20-person startup needs to decide how to enter a market currently dominated by three large incumbents.

**Branches:**
- A: Niche specialization — own a segment the incumbents under-serve
- B: Distribution partnership — get embedded in an incumbent's ecosystem as a complement
- C: Price disruption — undercut on price and win on volume

*[Scoring and expansion would follow...]*

## Why this technique

Strategic planning has no single correct answer. Generating three distinct branches forces consideration of genuinely different approaches rather than anchoring on the first idea. Scoring before expansion prevents over-investing in analysis of a weak branch.

## When to escalate

If the branches need deeper sub-analysis → use prompt chaining (Rung 4): one prompt per branch for detailed analysis before the final selection prompt.
