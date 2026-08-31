---
task: "Whole-branch review without re-trusting the branch's own self-assessment"
category: quality-verification
summary: "Dispatch reviewers that never saw the build session, since a session that built something is the worst judge of it."
openingPrompt: "Review this whole branch without letting the session that built it grade its own work -- dispatch a fresh reviewer with the base and head SHAs who never saw the build session, run the diff-shaped toolkit reviewers in parallel for correctness, silent failures, and test coverage, check for contract drift, and if two verdicts disagree, run the tribunal to decide it per criterion rather than deferring to whichever session sounds more confident."
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
dos:
  - "Dispatch a fresh reviewer with the base and head SHAs -- one that never saw the build session that produced the diff."
  - "Run the diff-shaped toolkit reviewers in parallel -- none of them fetches a PR itself, so the caller's scope lets them parallelize cleanly."
  - "Check for contract drift as a zero-setup addition to the review gate."
  - "Run the tribunal when two reviewers disagree, and decide it per criterion rather than by whichever session sounds more confident."
donts:
  - "Don't let the session that built something judge its own work -- it reviews the intent it remembers, not the diff it actually produced."
  - "Don't trust a self-assessment to catch what a branch left out -- that's exactly what self-assessment structurally can't see."
  - "Don't resolve a disagreement between reviewers by picking one over the other without running the tribunal to decide it per criterion."
---

# Whole-branch review without re-trusting the branch's own self-assessment

The failure mode is structural, not moral: a session that built something is the worst
available judge of it, because it reviews the intent it remembers rather than the diff it
produced. Every skill here is chosen for its blindness properties.
