---
task: "Rework a plugin to the official Anthropic standard"
category: plugin-authoring
summary: "Measure the instrument before the plugin, apply only the tiers a model can apply under a lock, and prove the rework rather than assert it — the order PR #56 established and nacharbeit ships."
openingPrompt: "Take this plugin through nacharbeit end to end: preflight what can be measured here, lint it for free, run the calibrated review, apply the haiku and sonnet findings under the fix lock, validate the manifest and structure once the files have changed, then prove one reworked wire with andon-verify instead of trusting the verifier's word."
external: ["claude-plugins-official"]
beats:
  - skill: "nacharbeit:nacharbeit-preflight"
    why: "Says what this environment can and cannot measure (no node, no viewer checker) and which other guards are live before a single token is spent — a finding on a rule that was silently skipped is worse than no finding."
    prompt: "what would nacharbeit check in this repo, and is anything blocking a run?"
  - skill: "nacharbeit:nacharbeit-lint"
    why: "Ninety script-checkable rules with no model in the loop, after the linter proves it can fail; everything a script can decide is decided here so the finders never have to."
    prompt: "lint plugins/lehre against the Anthropic plugin standard — frontmatter, hooks.json, scripts, the README"
  - skill: "nacharbeit:nacharbeit-review"
    why: "The finder grades a real file only after clearing a recall floor for every rule family on planted fixtures and a sealed hold-out; a reviewer with an unknown false-negative rate is an opinion, not a measurement."
    prompt: "review our plugins against the nacharbeit rubric and give me the backlog by model tier"
  - skill: "nacharbeit:nacharbeit-fix"
    why: "One remediator per file at the file's tier, a blind verifier that runs the file's post-checks, and a PreToolUse hook that denies every edit outside the lock — the write scope is a refusal, not a sentence a model may skip."
    prompt: "apply the haiku and sonnet findings from the review, one file at a time, and tell me what's left for me"
  - skill: "plugin-dev:plugin-validator"
    why: "Runs after the files have changed, not before: the manifest and structure validation nacharbeit's post-checks delegate to the runtime's own validator, on the reworked tree."
  - skill: "andon:andon-verify"
    why: "nacharbeit's verifier checks that an entry was applied and nothing regressed; whether the reworked skill actually fires and does its job is a wire to prove, and the fix skill hands off here by name."
grounding: "PR #56's own numbers: the calibrated finder still missed three sealed defects (rigidity form, script run-or-read intent, intra-plugin cannibalization), and the fix pass applied 274 of 297 entries while three hand fixes were needed for what a single-file blind verifier cannot see — a risk inversion in explore-branches.js, a confirmed-only gate in handbook-fix.js, a deleted tools line. Every beat above exists because one of those happened."
dos:
  - "Run preflight first and read its skipped list -- silence on a rule that could not run is not a pass."
  - "Let the review refuse: a family below its sealed floor, a completed:false return, or an open lock is a stop, not something to work around."
  - "Read the opus- and human-tier list the fix pass leaves for you; those are decisions the pipeline was built never to make."
  - "Prove one reworked wire with andon-verify before believing the pass -- the verifier confirms the edit landed, not that the skill works."
donts:
  - "Don't launch the review or the fix with hand-built args -- only the baked run.js and fix-run.js carry the leak assertions and the lock."
  - "Don't reach for NACHARBEIT_DISABLE_GUARD=1 or another plugin's escape hatch when the fix pass is denied -- report the denial and stop that file."
  - "Don't retune the finder or edit a fixture after seeing what it missed -- fix the rubric or add a fixture, then rerun from the calibration."
  - "Don't commit during the pass -- the guard denies it, and the diff is yours to read once the lock is released."
---

<RecipeHeader />

The order matters more than any single beat. Preflight says what can be measured;
lint decides everything a script can decide; the review calibrates its finder before
it grades a real file and refuses when a rule family falls below its floor; the fix
pass applies only the tiers a model can apply, under a hook that turns the write scope
into a refusal; the validator runs on the reworked tree, not the plan; and
`andon-verify` proves one wire, because a verifier that confirms an edit landed has
said nothing about whether the skill now works.

<RecipeBeats />
