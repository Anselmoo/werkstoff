---
task: "Audit a repo against its own documented conventions"
category: quality-verification
summary: "Documented rules and undocumented-but-real patterns are audited by different plugins on purpose -- blurring that line double-reports the same finding."
openingPrompt: "Extract the discrete, checkable rules this repo's own documentation states and audit the code against them first, then separately find any undocumented conventions the code has converged on and decide which variant should become canonical, get a second, adversarial judge on that canonization, and only simplify the code once both the documented and undocumented halves have actually settled."
external: ["claude-plugins-official"]
beats:
  - skill: "self-assess:self-assess-lint-audit"
    why: "Extracts discrete rules from .claude/house-rules.md, falling back to CLAUDE.md, capped at lint_max_rules -- the documented half of the audit."
    prompt: "extract the discrete, checkable rules this repo's own documentation states, and audit the code against them"
  - skill: "self-assess:convention-auditor"
    why: "Find plus Verify over the extracted rules -- a documented rule with no verified violation is not the same claim as a followed rule."
  - skill: "codebase-consistency:pattern-extractor"
    why: "Handles the undocumented half explicitly, refusing to force a pick when the signal between competing patterns is genuinely tied."
    prompt: "find any undocumented conventions this codebase has converged on inconsistently, and tell me which variant should become canonical"
  - skill: "codebase-consistency:consistency-critic"
    why: "Second judge -- catches forced consistency and a PASS verdict that was rubber-stamped rather than re-derived from the evidence."
  - skill: "pr-review-toolkit:code-simplifier"
    why: "Runs last, on the now-aligned code only -- simplifying before the convention is settled means simplifying twice."
grounding: "plugins/codebase-consistency/README.md's own scope section routes documented conventions and version-deprecated idioms out of codebase-consistency and into self-assess -- beats 1-2 and 3-4 above sit on opposite sides of that line by design, and a recipe that blurs it double-reports the same finding from both plugins."
dos:
  - "Audit the documented half first -- extract discrete rules from the repo's own documentation and verify real violations, not just their presence."
  - "Handle undocumented conventions as a separate pass, and refuse to force a canonical pick when the signal between variants is genuinely tied."
  - "Get a second judge on any canonization to catch forced consistency or a rubber-stamped verdict."
  - "Simplify last, only once the convention question is actually settled -- simplifying before that means simplifying twice."
donts:
  - "Don't audit documented and undocumented conventions with the same pass -- they're handled by different plugins on purpose, and blurring the line double-reports the same finding."
  - "Don't force a canonical pick when two variants are genuinely tied on frequency, maturity, and recency."
  - "Don't simplify the code before the convention question is settled -- that means doing the simplification twice."
---

<RecipeHeader />

Documented rules and undocumented-but-real patterns are audited by different plugins on
purpose. Run the documented half first against the repo's own house rules, then hand the
undocumented half to codebase-consistency to find and canonize, and only simplify once
both halves have settled -- blurring that line is how the same finding gets reported twice.

<RecipeBeats />
