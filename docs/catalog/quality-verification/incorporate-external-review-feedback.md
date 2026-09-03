---
task: "Incorporate external review feedback"
category: quality-verification
summary: "Take review feedback on its own terms without defending, then confirm the loop actually closed, not just that something changed nearby."
external: ["superpowers"]
beats:
  - skill: "superpowers:receiving-code-review"
    why: "The instinct to defend is strongest immediately; the skill exists to interrupt it."
    prompt: "here's the review feedback. Work through it properly — separate what has to change from what's preference, and don't argue with the reviewer."
  - skill: "compass:compass-draft-revise"
    why: "Applies only when the artifact is prose; it rates 1-5 per criterion and revises only what falls at or below threshold."
    prompt: "score this doc against the reviewer's criteria and fix only what falls below the bar"
  - skill: "superpowers:verification-before-completion"
    why: "\"Addressed the comments\" and \"the comment's concern is gone\" are different claims."
    prompt: "for each review comment, show me the change that resolves it — not just that something changed nearby"
grounding: "applying a reviewer's finding to `docs/plugin-authoring/references/craft-standards.md` is the document case where `compass-draft-revise` genuinely applies; the same finding applied to a plugin's `SKILL.md` behavior is a code change and belongs in the review entry above."
---

<RecipeHeader />

**No werkstoff fit — this is pure Superpowers.** `superpowers:receiving-code-review` owns
this task end to end: reading feedback without defensiveness, separating what must change
from what is preference, and closing the loop. `compass:compass-draft-revise` is the
nearest candidate but is scoped to prose, not code.

<RecipeBeats />
