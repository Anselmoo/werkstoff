---
task: "Tune an instruction a workflow will reuse"
category: quality-verification
summary: "Anchoring an ambiguous output shape to concrete examples, then scoring competing phrasings against real test cases -- prompt tuning with evidence, not just a rewrite by feel."
external: ["claude-plugins-official"]
beats:
  - skill: "compass:compass-calibrate-format"
    why: "Anchors an ambiguous output shape to 2-5 concrete examples instead of adding more prose describing the shape."
    prompt: "this instruction's output format keeps coming out wrong -- give me a few concrete examples of exactly the shape I want instead of more description"
  - skill: "compass:compass-optimize-instruction"
    why: "Generates one candidate per framing and scores each against real test cases -- explicitly not intended for a one-off prompt with no test cases to score against."
  - skill: "plugin-dev:skill-development"
    why: "If the tuned instruction is going to live inside a SKILL.md, the frontmatter and description rules are what actually decide whether it ever fires."
  - skill: "compass:compass-reason-verify"
    why: "A 4-rung effort ladder applied to the resulting instruction's own failure risk, once the wording itself is settled."
grounding: "tools/plugin-serializer/'s generator prompt: this repo's CLAUDE.md records that its YAML-frontmatter traps had to be named explicitly in the prompt before sonnet reliably stopped producing them, and that opus bought nothing extra on the same task -- a tuned instruction with a measured pass/fail history, exactly beat 2's precondition."
---

<RecipeHeader />

Anchor an ambiguous output shape to concrete examples before reaching for more descriptive
prose, then score competing phrasings against real test cases rather than picking by feel.
If the tuned instruction is destined for a SKILL.md, its frontmatter and description are
what decide whether it fires at all, so settle the wording before shipping it there.

<RecipeBeats />
