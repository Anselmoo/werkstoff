---
task: "Diagnose a pipeline red across several jobs"
category: ci-release
summary: "Tell apart one cause with many symptoms from several unrelated causes before debugging any single red job."
external: ["superpowers"]
beats:
  - skill: "self-assess:self-assess-ci-topology"
    why: "A config-level defect explains all the symptoms at once; chasing symptoms first wastes the whole first pass."
    prompt: "several CI jobs went red at once — audit the CI config itself before we look at any individual failure"
  - skill: "compass:compass-decompose-chain"
    why: "Derives which failures are genuinely independent and can be worked in parallel, from the dependency graph rather than by guess."
    prompt: "break these five red jobs into independent tracks — tell me what depends on what and what can be worked in parallel"
  - skill: "superpowers:systematic-debugging"
    why: "Required before proposing any fix; a fix proposed ahead of a root cause is a second failure mode."
    prompt: "work the lint failure to root cause first — no fixes proposed until the cause is nailed down"
grounding: "`.github/workflows/plugin-checks.yml` runs seven checks with `continue-on-error: true` and collapses them into a single \"Fail the job if any check failed\" step. One red job can therefore mean any of seven independent causes, which is exactly the shape this entry exists to untangle."
---

<RecipeHeader />

Several jobs red at once is usually one cause with several symptoms, or several unrelated
causes that must not be debugged as one. The first move is telling those two cases apart.

<RecipeBeats />
