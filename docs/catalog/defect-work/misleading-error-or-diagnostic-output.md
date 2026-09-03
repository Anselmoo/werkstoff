---
task: "Fix misleading error or diagnostic output"
category: defect-work
summary: "Treat error messages as a first-class surface and check they aren't the visible half of a suppressed failure."
external: ["claude-plugins-official"]
beats:
  - skill: "cupertino:cupertino-elevate"
    why: "Its frontmatter scopes it to \"a low-status commodity feature already in scope for the current build - error messages, logs, config, settings, onboarding.\""
    prompt: "our error messages are technically accurate and completely useless. Treat them as a first-class surface, not an afterthought."
  - skill: "pr-review-toolkit:silent-failure-hunter"
    why: "A misleading message is often the visible half of a suppressed error; fixing the wording alone leaves the suppression."
    prompt: "this error text points at the wrong cause — check whether something upstream is swallowing the real failure"
  - skill: "pr-review-toolkit:comment-analyzer"
    why: "Comment rot and message rot come from the same edit that moved the behavior."
    prompt: "check whether the comments around this error path still describe what the code does"
grounding: "the resolve step in `.github/workflows/plugin-release.yml` exits with `Unknown plugin group '$GROUP' from tag '$TAG'` — accurate, but silent on the fact that the allowed set is a hardcoded eight-name `case` list in the same file, which is what a reader actually needs to know."
---

<RecipeHeader />

An error message that names the wrong cause costs more than no message at all, because it
buys a confident wrong hypothesis. This is the one commodity surface `cupertino` claims
explicitly, and the pairing is easy to miss.

<RecipeBeats />
