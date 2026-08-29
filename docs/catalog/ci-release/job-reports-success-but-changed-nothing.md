---
task: "Investigate a job that reports success but changed nothing"
category: ci-release
summary: "Hunt the silent success — a green exit code whose supposed effect never actually happened."
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
---

The most expensive CI defect is the green one. A job exits zero, the badge stays green,
and the work it was supposed to do never happened. Conditional skips, swallowed errors,
and unmatched patterns all produce this shape.
