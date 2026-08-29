---
task: "Propagate a vendored artifact to N copies"
category: change-existing-code
summary: "Enumerate every copy, fan updates out in parallel, then prove the tree and lock agree afterwards."
external: ["superpowers"]
beats:
  - skill: "compass:compass-map-relationships"
    why: "The count must be exhaustive before the first write; a missed copy is silent drift."
    prompt: "list every vendored copy of this artifact and the canonical source they're supposed to track"
  - skill: "superpowers:dispatching-parallel-agents"
    why: "Multiple dispatch calls in one response run in parallel, one per response runs sequentially."
    prompt: "update all seven vendored copies in parallel — one agent per copy, all dispatched in the same message, mechanical tier model"
  - skill: "andon:andon-verify"
    why: "The lock is the stated contract; a successful copy loop is not evidence that it holds."
    prompt: "prove the working tree now matches the committed artifact lock — strictly"
grounding: "`inline-d3.html` exists in the seven `plugins/*/assets/` directories that carry one plus the canonical `tools/d3-subset/inline-d3.html`, and CI already carries the proof step: `plugin-checks.yml` runs `rrt artifacts --check --strict` specifically so a dropped copy fails a job instead of denying an edit months later."
---

Propagation is mechanical, parallel, and unforgiving: N-1 updated copies is a worse state
than zero updated copies, because the drift is now invisible.
