---
task: "Sweep documentation drift after a change"
category: surface
summary: "Sweep every documentation claim for drift immediately after a change, while the diff that caused it is still legible."
external: ["claude-plugins-official"]
beats:
  - skill: "self-assess:self-assess-docs-drift"
    why: "Verifies every extracted, in-scope claim against the current codebase; run months later it produces a backlog instead of a fix."
    prompt: "we renamed several things this week — check whether the docs still describe what the code actually does"
  - skill: "pr-review-toolkit:comment-analyzer"
    why: "Comments drift from the same edit as docs, and no docs sweep reads them."
    prompt: "check the comments in the files this change touched — are any of them now describing behavior that moved?"
  - skill: "codebase-consistency:pattern-analyst"
    why: "Genuinely post-hoc; a convention survey run before the content is correct clusters variants of the wrong text."
    prompt: "now that the docs are accurate, survey how docstrings are actually written across this repo and cluster the variants"
grounding: "this repo generates part of its own documentation surface: `.rrt.toml` declares `[[tool.rrt.docs.shared_blocks]]`, which is what regenerates the `rrt:auto:start:example-prompts-intro` block visible at the top of every plugin README's Example Prompts section — so a drift sweep must distinguish generated prose from hand-written prose before reporting either."
---

Docs drift is asymmetric: the code moves and the prose does not, so the drift is always in
the same direction and is never announced. The cheapest catch is a claim-level sweep
immediately after the change, while the diff is still legible.
