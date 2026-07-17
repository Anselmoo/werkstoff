---
name: self-consistency-logic-puzzle
description: >-
  Solves a logic puzzle using self-consistency: three independent reasoning
  paths followed by majority-vote selection. Use when a single reasoning
  pass may be unreliable and the correct answer is unique.
---

You are solving a logic puzzle. Reason through it three times independently,
using a different strategy each time. After all three attempts, identify
which answer appeared most often and declare it the final answer.

Puzzle: {{PUZZLE_TEXT}}

---

## Attempt 1 — Forward deduction
Work from the given facts forward, eliminating impossible options.

[Claude reasons here]

**Answer 1:** ___

---

## Attempt 2 — Backward from options
Start with each possible answer and check which one is consistent with all facts.

[Claude reasons here]

**Answer 2:** ___

---

## Attempt 3 — Constraint mapping
List all constraints explicitly, then check which answer satisfies all of them simultaneously.

[Claude reasons here]

**Answer 3:** ___

---

## Final answer

Majority result: ___ (appeared ___ / 3 times)

If all three answers disagree, identify the one supported by the strongest reasoning chain and explain why the others failed.

## Example puzzle

**Puzzle:** Alice, Bob, and Carol each have a different pet (cat, dog, bird). Alice does not have the dog. The person with the bird lives next door to Carol. Bob has the cat. Who has the bird?

**Attempt 1 (forward):** Bob has cat → Alice and Carol have dog/bird → Alice not dog → Alice has bird → Carol has dog.  
**Attempt 2 (backward):** If Carol has bird, she'd live next to herself — impossible. If Bob has bird, Bob has cat and bird — impossible. Alice has bird.  
**Attempt 3 (constraints):** Constraint "Alice not dog" + "Bob has cat" → Alice has bird.  
**Final answer:** Alice (3/3)

## Why this technique

Logic puzzles have a unique correct answer but multiple reasoning paths. Running three passes catches cases where one path makes an early wrong assumption. Majority vote is more reliable than a single chain.

## When to escalate

If the puzzle requires more than ~10 logical steps → use prompt chaining (Rung 4) to solve one sub-problem per stage rather than fitting all three attempts in a single turn.
