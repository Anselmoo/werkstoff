---
task: "Run a read-only design study with an evidence legend"
category: before-any-code
summary: "Produce a citation-bearing study of how something works, marking every claim [V]erified or [P]rovisional, before anyone touches it."
external: []
beats:
  - skill: "compass:compass-investigate-dynamically"
    why: "The next thing worth reading is decided by the last observation; a pre-planned file list misses it."
    prompt: "read-only please: I want to understand how this works before anyone changes it. Don't edit a single file."
  - skill: "compass:compass-ground-evidence"
    why: "The [V]/[P] split is exactly this skill's file:line-or-flagged-prior-knowledge rule."
    prompt: "write this up with a legend: [V] for anything you can cite a file:line for, [P] for anything you're inferring. Nothing unmarked."
  - skill: "compass:compass-map-relationships"
    why: "Multi-hop claims need a traversable triple index, not recollection."
    prompt: "trace how a change in the shared script would reach each plugin's output"
  - skill: "compass:compass-summarize-trace"
    why: "A study whose reasoning is not reconstructible cannot be audited by its reader"
grounding: "a read-only study of how the four werkstoff `PreToolUse` hooks interact, covering `plugins/andon/hooks/`, `plugins/self-assess/hooks/`, `plugins/confab/hooks/`, and `plugins/cupertino/hooks/`, with each interaction marked [V] or [P]."
---

A design study is worth reading only if its confidence is legible. The trap is a study
that mixes what was checked with what was assumed and marks neither. A two-symbol legend
fixes it: **[V]** for a claim carrying a file:line or URL, **[P]** for a claim that is
provisional — inferred, plausible, and explicitly flagged as unverified.
