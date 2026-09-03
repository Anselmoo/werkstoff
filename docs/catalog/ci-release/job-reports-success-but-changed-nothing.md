---
task: "Investigate a job that reports success but changed nothing"
category: ci-release
summary: "Hunt the silent success — a green exit code whose supposed effect never actually happened."
openingPrompt: "This job exits zero but nothing downstream actually changed -- hunt for swallowed errors and silent skips first, then prove the wire that the job is supposed to produce an effect rather than trusting the exit code, and check whether anything would even fail if it silently did nothing again."
external: ["claude-plugins-official"]
beats:
  - skill: "pr-review-toolkit:silent-failure-hunter"
    why: "Purpose-built for exactly this shape: silent failures, inadequate error handling, and fallback behavior that suppresses the real outcome."
    prompt: "this job exits zero but nothing downstream changed — go hunt for swallowed errors, skipped branches, and fallbacks that hide the real outcome"
  - skill: "andon:andon-verify"
    why: "A green exit code is not evidence; the wire \"job ran → artifact changed\" has to be proven independently."
    prompt: "prove the wire: this job is supposed to produce a version bump. Show me evidence it did, not that it exited zero."
  - skill: "confab:confab-assertion-audit"
    why: "If nothing asserts the job's effect, the next silent skip is invisible again."
    prompt: "is there any test or check that would fail if this job silently did nothing?"
grounding: "`.github/workflows/auto-version-bump.yml` skips entirely when the head commit message does not start with a recognized conventional-commit type; its own header comment records that a plain-English PR title \"is silently skipped, by design\". The run is green and bumps nothing — the exact shape `silent-failure-hunter` is built for."
dos:
  - "Hunt for swallowed errors, skipped branches, and fallbacks that hide the real outcome -- that's exactly this failure's shape."
  - "Prove the job's supposed effect independently -- a green exit code by itself is not evidence anything happened."
  - "Check whether any test or assertion would fail if the job silently did nothing -- if not, the next silent skip is invisible again."
donts:
  - "Don't trust a green exit code as proof a job did what it claims -- the most expensive CI defect is exactly the green one that changed nothing."
  - "Don't assume a conditional skip is announced -- this repo has one that's silent by its own design, documented in its own header comment."
  - "Don't leave the job's effect unasserted -- nothing catching a silent skip once means nothing will catch it the next time either."
---

<RecipeHeader />

The most expensive CI defect is the green one. A job exits zero, the badge stays green,
and the work it was supposed to do never happened. Conditional skips, swallowed errors,
and unmatched patterns all produce this shape.

<RecipeBeats />
