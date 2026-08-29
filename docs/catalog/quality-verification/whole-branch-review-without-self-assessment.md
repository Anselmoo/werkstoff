---
task: "Whole-branch review without re-trusting the branch's own self-assessment"
category: quality-verification
summary: "Dispatch reviewers that never saw the build session, since a session that built something is the worst judge of it."
external: ["superpowers", "claude-plugins-official"]
beats:
  - skill: "superpowers:requesting-code-review"
    why: "Dispatches a `general-purpose` subagent filling `code-reviewer.md` with BASE_SHA / HEAD_SHA — a reviewer that never saw the build session."
    prompt: "request a code review of this branch against main — a fresh reviewer, not you, and give it the base and head SHAs"
  - skill: "pr-review-toolkit:code-reviewer"
    why: "All six toolkit agents (including silent-failure-hunter and pr-test-analyzer) are diff-shaped and none fetches a PR itself; the caller passes scope, so they parallelize cleanly."
    prompt: "review this diff four ways in parallel — general correctness, silent failures, test coverage, type design. Most capable model for the whole-branch pass."
  - skill: "pr-review-toolkit:silent-failure-hunter"
    why: "All six toolkit agents are diff-shaped and none fetches a PR itself; the caller passes scope, so they parallelize cleanly."
  - skill: "pr-review-toolkit:pr-test-analyzer"
    why: "All six toolkit agents are diff-shaped and none fetches a PR itself; the caller passes scope, so they parallelize cleanly."
  - skill: "confab:confab-contract-drift"
    why: "Drops into a review gate with zero setup, and catches what a prose review reads past."
  - skill: "andon:andon-verify"
    why: "Its tribunal is explicitly \"never authored or influenced by the session that proposed or built the fix under review.\""
    prompt: "two reviewers disagree about whether this actually satisfies the requirement. Run the tribunal and decide it per criterion."
grounding: "a branch touching all five plugin-local copies of `build_symbol_index.py` plus `tools/symbol-indexer/` — a diff whose risk is entirely in what it left out, which is precisely what a self-assessment cannot see."
---

The failure mode is structural, not moral: a session that built something is the worst
available judge of it, because it reviews the intent it remembers rather than the diff it
produced. Every skill here is chosen for its blindness properties.
