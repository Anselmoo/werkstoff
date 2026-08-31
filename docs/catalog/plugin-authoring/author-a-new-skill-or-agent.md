---
task: "Author a new skill or agent for a plugin"
category: plugin-authoring
summary: "The frontmatter spec, the loop shape, and a triggering-effectiveness review — in that order, because a skill that never fires reports no error and only a dedicated review catches it."
openingPrompt: "I'm writing a new skill for this plugin -- walk me through the frontmatter and structure conventions first, use the writing-skills loop to actually draft and verify it, then review the description specifically for whether it will actually trigger, audit it for agentic-reliability defects, and only validate the manifest once the components genuinely exist."
external: ["superpowers", "claude-plugins-official"]
beats:
  - skill: "plugin-dev:skill-development"
    why: "The canonical frontmatter and progressive-disclosure spec, with good-vs-bad description: examples shown side by side — the reference this whole task is judged against."
    prompt: "I'm writing a new skill for this plugin — walk me through the frontmatter and structure conventions before I draft anything"
  - skill: "superpowers:writing-skills"
    why: "Explicitly for creating new skills, editing existing ones, or verifying a skill works before deployment — the loop shape plugin-dev's reference material doesn't itself supply."
  - skill: "plugin-dev:skill-reviewer"
    why: "Reviews triggering effectiveness specifically — a skill with a weak description never fires, and nothing else in this sequence would catch that."
    prompt: "review this skill's description and frontmatter for triggering effectiveness — will this actually fire when it should?"
  - skill: "confab:confab-agentic-reliability"
    why: "Checks for excessive tool grants and missing verify-wiring — the werkstoff-side beat that catches what a style/triggering reviewer reads past."
    prompt: "audit this new skill/agent for agentic reliability defects — unbounded retries, missing verification wiring, tool grants beyond its stated role"
  - skill: "plugin-dev:plugin-validator"
    why: "Manifest and structure, checked last, once the components actually exist — validating a manifest before the skill exists checks nothing real."
grounding: "This repo's own CLAUDE.md finding: frontmatter that fails to parse still loads, with no description and no tools, so the skill never triggers and nothing reports an error — which is exactly why test/plugins/lint-frontmatter.py exists and why the skill-reviewer beat here can't be skipped."
dos:
  - "Learn the canonical frontmatter and progressive-disclosure spec before drafting anything new."
  - "Use the writing-skills loop to create, edit, and verify the skill -- the authoring loop the frontmatter spec alone doesn't supply."
  - "Review the description specifically for triggering effectiveness -- a weak description never fires and nothing else in the sequence catches that."
  - "Audit the new skill or agent for excessive tool grants and missing verify-wiring before shipping it."
  - "Validate the manifest last, once the components actually exist -- validating it earlier checks nothing real."
donts:
  - "Don't skip the triggering-effectiveness review -- a skill that never fires reports no error at all, indistinguishable from a skill nobody needed."
  - "Don't validate the plugin manifest before the skill/agent files actually exist -- there's nothing real to check yet."
  - "Don't assume frontmatter that looks fine actually parses -- malformed frontmatter still loads, silently, with no description and no tools."
  - "Don't skip the agentic-reliability audit just because the description and structure already passed review -- it catches a different category of defect entirely."
---

# Author a new skill or agent for a plugin

A new skill or agent that never fires reports no error at all — it just sits unused,
indistinguishable from a skill nobody needed. `plugin-dev:skill-development` supplies the
frontmatter spec and `superpowers:writing-skills` the authoring loop, but neither one
checks whether the description will actually trigger; that is `plugin-dev:skill-reviewer`'s
job specifically. `confab:confab-agentic-reliability` catches what a style/triggering
review reads past — excessive tool grants and missing verify-wiring — and
`plugin-dev:plugin-validator` runs last, once there is a real manifest to validate against.
