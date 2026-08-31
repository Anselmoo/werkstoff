---
task: "Tune an instruction a workflow will reuse"
category: quality-verification
summary: "Anchoring an ambiguous output shape to concrete examples, then scoring competing phrasings against real test cases -- prompt tuning with evidence, not just a rewrite by feel."
openingPrompt: "This reused instruction's output keeps coming out wrong -- anchor the shape to a few concrete examples instead of more descriptive prose, then score competing phrasings against real test cases rather than picking by feel, check the frontmatter rules if it's going to live in a SKILL.md, and finally run an effort-ladder check on the settled wording's own failure risk."
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
dos:
  - "Anchor an ambiguous output shape to 2-5 concrete examples before adding more descriptive prose."
  - "Score competing phrasings against real test cases -- this only works when real test cases actually exist to score against."
  - "Check the frontmatter and description rules if the tuned instruction is destined for a SKILL.md -- they decide whether it fires at all."
  - "Run the effort-ladder check on the resulting instruction's own failure risk only once the wording itself is settled."
donts:
  - "Don't add more descriptive prose to fix an ambiguous output shape -- anchor it to concrete examples instead."
  - "Don't reach for compass-optimize-instruction on a one-off prompt with no test cases to score against."
  - "Don't ship a tuned instruction into a SKILL.md without checking whether its frontmatter and description will actually make it fire."
---

# Tune an instruction a workflow will reuse

Anchor an ambiguous output shape to concrete examples before reaching for more descriptive
prose, then score competing phrasings against real test cases rather than picking by feel.
If the tuned instruction is destined for a SKILL.md, its frontmatter and description are
what decide whether it fires at all, so settle the wording before shipping it there.
