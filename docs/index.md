---
layout: home

hero:
  name: werkstoff
  text: A workshop of Claude Code plugins
  tagline: Nine plugins that each catch one distinct failure mode, and a catalog of what to say to reach them at the moment they still help.
  actions:
    - theme: brand
      text: Prompt catalog
      link: /catalog/
    - theme: alt
      text: Orchestration overview
      link: /orchestration/
    - theme: alt
      text: View on GitHub
      link: https://github.com/Anselmoo/werkstoff

features:
  - title: Indexed by task, not by plugin
    details: Thirty-seven development tasks, each broken into beats naming the skill that fires there and why it belongs there rather than later. Ninety-eight copy-paste prompts.
    link: /catalog/
    linkText: Open the catalog
  - title: Every prompt each plugin answers
    details: The example prompts from all nine plugin READMEs, collected on one page and generated from the READMEs themselves so the list cannot drift out of date.
    link: /prompt-index
    linkText: Browse by plugin
  - title: Which pipeline owns the task
    details: Four pipelines share the same eight-step skeleton and compete rather than compose. The routing table names which one owns a given task shape, and which to leave alone.
    link: /orchestration/references/routing
    linkText: Read the routing table
  - title: What happens when they share a session
    details: Five plugins register a PreToolUse hook, two diff baselines can disagree, and two agents can collide on a name. The hazards, with their inert conditions and escape hatches.
    link: /orchestration/references/hazards
    linkText: Read the hazards
---

## Nine plugins, one job each

Pick by problem, not by feature list — each plugin targets one distinct failure mode
and refuses to speak outside it. Every card below opens its full README in this
site — same install instructions and licensing as the [repo](https://github.com/Anselmoo/werkstoff),
without leaving for it.

- **[`self-assess`](/plugins/self-assess)** — codebase self-assessment: stage/wire mapping, docs-vs-code drift, CI/CD topology, house-rules enforcement, multi-repo dashboard.
- **[`confab`](/plugins/confab)** — catches AI confabulation: hallucinated dependencies, assertion-less tests, contract drift, unreliable agentic loops.
- **[`compass`](/plugins/compass)** — a prompt-engineering technique library composed by `compass-solve` into a clarify → explore → decompose → execute → revise pipeline.
- **[`cupertino`](/plugins/cupertino)** — a Steve-Jobs-grounded design and craft discipline for a project's whole lifecycle.
- **[`andon`](/plugins/andon)** — an evidence-grounded harden-and-advance loop: propose maximally, verify adversarially, never advance past an unproven wire.
- **[`cli-scaffold`](/plugins/cli-scaffold)** — scaffolds production-grade CLIs across 12 languages against a frozen five-pillar doctrine.
- **[`codebase-consistency`](/plugins/codebase-consistency)** — harmonizes undocumented pattern variants in an already-modern, live codebase.
- **[`takt`](/plugins/takt)** — enforces declared beat order at the tool-call layer; inert until a repo declares its beats.
- **[`lehre`](/plugins/lehre)** — researches a code style, pattern and architecture doctrine, then denies the write that would violate it.
