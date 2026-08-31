---
task: "Perform a same-stack version uplift"
category: change-existing-code
summary: "Identify the breaking changes that actually bite this codebase, then apply mechanical modernization fixes one cluster at a time."
openingPrompt: "We're moving this codebase up a major version of the same stack -- find which breaking changes actually affect our code first, then judge our idioms against the version we actually target rather than the newest one, check that any new replacement dependencies actually exist, and apply only the mechanical modernization fixes, one cluster at a time."
external: ["claude-plugins-official"]
beats:
  - skill: "code-modernization:version-delta-analyst"
    why: "`modernize-brief.md:36` explicitly sanctions spawning this agent directly; the surrounding pipeline hard-refuses without artifacts this task has no reason to produce."
    prompt: "we're moving this codebase up a major version of the same stack. Which breaking changes actually affect our code?"
  - skill: "self-assess:self-assess-code-idiom"
    why: "Judges idioms against the version the repo actually targets, not against the newest one."
    prompt: "find deprecated idioms in this repo, judged against the version we actually target — not the latest one"
  - skill: "confab:confab-dependency-audit"
    why: "An uplift is when a plausible-but-nonexistent replacement package is most likely to be introduced"
  - skill: "self-assess:self-assess-idiom-fix"
    why: "Dispatches one remediator per (file, kind) cluster, never a batch spanning files."
    prompt: "apply the mechanical modernization fixes only — leave anything needing judgment for me"
grounding: "`tools/werkstoff-cli/pyproject.toml` declares `requires-python = \">=3.12\"` and `target-version = \"py312\"`, so any idiom finding must be judged against 3.12 — flagging a pre-3.12 replacement as \"modern\" would be a regression dressed as an uplift."
dos:
  - "Dispatch version-delta-analyst directly for the breaking-change catalog rather than adopting the whole eight-stage pipeline."
  - "Judge idioms against the version the repo's manifest actually declares, not the newest version available."
  - "Check any new replacement package actually exists -- an uplift is exactly when a plausible-but-nonexistent one is most likely to get introduced."
  - "Apply mechanical fixes one (file, kind) cluster at a time, never batched across files."
donts:
  - "Don't judge idioms against the newest available version -- self-assess-code-idiom judges against what the manifest already declares, not a target it hasn't reached."
  - "Don't run the idiom audit before the uplift -- that measures the old world, not the new one."
  - "Don't batch mechanical fixes across multiple files in one remediation pass."
---

# Perform a same-stack version uplift

A same-stack uplift preserves code and tweaks it; it is not a rewrite from intent. The
right tool for it lives inside `code-modernization`, and the right way to use it is to
dispatch the one agent directly rather than adopt the eight-stage pipeline around it.
