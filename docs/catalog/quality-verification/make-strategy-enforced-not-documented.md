---
task: "Make a strategy enforced rather than documented"
category: quality-verification
summary: "Move a rule from prose that only suggests to a PreToolUse hook that actually blocks, once divergence from it is measured."
openingPrompt: "Turn this documented convention into something that actually holds -- draft it as one concrete rule with real file:line evidence, check the real files against that rule to see where it actually diverges before writing any enforcement, and then write a PreToolUse hook that blocks it on the first attempt rather than trusting prose to hold."
external: ["claude-plugins-official"]
beats:
  - skill: "cupertino:cupertino-handbook-draft"
    why: "A rule stated abstractly cannot be mechanically checked; the draft step forces a real file:line basis."
    prompt: "turn this convention into one concrete rule with real file:line evidence — not a principle, a rule"
  - skill: "cupertino:cupertino-handbook-check"
    why: "Enforcement written before the divergence is known will either block everything or nothing."
    prompt: "check these files against that rule and show me every divergence with a line number"
  - skill: "plugin-dev:hook-development"
    why: "A `PreToolUse` hook holds regardless of model cooperation; prose does not."
    prompt: "prose isn't holding this. Write a PreToolUse hook that blocks it on the first attempt."
grounding: "the enforcement ladder measured in this repo's own `CLAUDE.md` — prose in a `SKILL.md` as baseline, a guard behind a fenced `python3` block invoked one run in three, a guard inside a Workflow script one in fourteen, and a `PreToolUse` hook of `type: \"command\"` blocked on the first attempt. `tools/enforcement-audit/rules/` currently holds a single `andon.json`; six plugins have no rules file at all."
dos:
  - "Draft the rule as one concrete, file:line-grounded statement -- an abstract principle can't be mechanically checked."
  - "Check real divergence against the rule before writing enforcement -- written blind, it will either block everything or nothing."
  - "Write a PreToolUse hook of type 'command' for anything that must hold regardless of model cooperation -- prose alone does not hold."
donts:
  - "Don't write enforcement before you know where the real divergence actually is -- it'll either block everything or nothing."
  - "Don't trust prose in a SKILL.md to actually enforce a rule -- this repo has measured it as the weakest layer on the enforcement ladder."
  - "Don't leave a rule that must hold universally sitting only in a fenced script or workflow-script guard -- those fire far less reliably than a PreToolUse hook."
---

# Make a strategy enforced rather than documented

A rule that lives only in prose is a suggestion. This repo has measured the difference,
and the measurement is what makes the entry actionable rather than moralistic.
