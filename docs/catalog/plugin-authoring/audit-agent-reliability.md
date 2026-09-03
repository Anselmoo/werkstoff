---
task: "Audit your own agent and skill definitions for loop-reliability defects"
category: plugin-authoring
summary: "The after-the-fact half of authoring: a fixed-category reliability sweep, a read-only confirmation pass, and a check against the canonical tools/description spec — never widening a grant to fix a finding about that same grant."
openingPrompt: "Sweep our own skills, agents, and workflows for agentic-reliability defects -- unbounded loops, missing escalation, no verify-wiring, tool grants beyond the stated role -- confirm any excessive-grant finding with a strictly read-only auditor, judge it against the canonical tools/description spec, and then prove any fix actually holds rather than just existing in prose."
external: ["claude-plugins-official"]
beats:
  - skill: "confab:confab-agentic-reliability"
    why: "Four fixed categories — unbounded retries, absent escalation, missing verify-wiring, excessive tool grants — run with verification on by default."
    prompt: "sweep our skills, agents, and workflows for agentic-reliability defects — unbounded loops, no escalation path, no verify wiring, tool grants beyond the stated role"
  - skill: "confab:agentic-reliability-auditor"
    why: "Read-only by its own tool grant (Read, Glob, Grep only) — it cannot 'fix' an excessive-tool-grant finding by widening its own grant, which is the exact failure mode this beat exists to avoid."
  - skill: "plugin-dev:agent-development"
    why: "Supplies the canonical tools:/description: spec the audit is judged against — without it, 'excessive' has no baseline to be excessive relative to."
  - skill: "andon:andon-verify"
    why: "'The guard exists' and 'the guard runs' are different claims — the distinction this repo has been burned by repeatedly, and the reason a reliability finding needs proof, not just a report."
grounding: "The unresolved self-assess:arch-health-auditor tool-grant anomaly recorded in this repo's own CLAUDE.md — it reports only {Read, Bash} against three different declared tools: formats tried, including in a fresh claude --print process. A live, currently-open case where a declared grant and the runtime grant disagree and no existing beat in this catalog would have caught it before this recipe existed."
dos:
  - "Sweep the four fixed reliability categories with verification on by default, not just a Find pass."
  - "Confirm an excessive-tool-grant finding with a strictly read-only auditor -- one that can't paper over the finding by widening its own grant."
  - "Judge any 'excessive' tool grant against the canonical tools:/description: spec -- without a baseline, excessive has nothing to be excessive relative to."
  - "Prove a fix actually runs with andon-verify -- 'the guard exists' and 'the guard runs' are different claims this repo has been burned by conflating."
donts:
  - "Don't let an agent fix its own excessive-tool-grant finding by widening its own grant -- that's the exact failure mode a read-only auditor exists to avoid."
  - "Don't judge a tool grant as excessive without the canonical spec as a baseline."
  - "Don't treat a reliability finding as resolved just because a guard was written -- confirm it actually runs, the way this repo's own unresolved arch-health-auditor tool-grant anomaly still hasn't been."
---

<RecipeHeader />

This is the after-the-fact half of authoring, run against skills and agents that already
exist. `confab:confab-agentic-reliability` sweeps four fixed categories with verification
on by default; `confab:agentic-reliability-auditor` is deliberately read-only, so it cannot
paper over an excessive-tool-grant finding by widening its own grant. `plugin-dev:agent-development`
supplies the canonical `tools:`/`description:` spec a finding of "excessive" is judged
against, and `andon:andon-verify` closes the gap between a guard that exists in prose and
a guard that actually runs.

<RecipeBeats />
