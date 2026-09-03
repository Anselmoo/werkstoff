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
    details: Twenty-five development tasks, each broken into beats naming the skill that fires there and why it belongs there rather than later. Seventy-six copy-paste prompts.
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
and refuses to speak outside it. Full descriptions, install instructions, and licensing
live in the [repo README](https://github.com/Anselmoo/werkstoff#plugins).

- **[`self-assess`](https://github.com/Anselmoo/werkstoff/blob/main/plugins/self-assess/README.md)** — codebase self-assessment: stage/wire mapping, docs-vs-code drift, CI/CD topology, house-rules enforcement, multi-repo dashboard.
- **[`confab`](https://github.com/Anselmoo/werkstoff/blob/main/plugins/confab/README.md)** — catches AI confabulation: hallucinated dependencies, assertion-less tests, contract drift, unreliable agentic loops.
- **[`compass`](https://github.com/Anselmoo/werkstoff/blob/main/plugins/compass/README.md)** — a prompt-engineering technique library composed by `compass-solve` into a clarify → explore → decompose → execute → revise pipeline.
- **[`cupertino`](https://github.com/Anselmoo/werkstoff/blob/main/plugins/cupertino/README.md)** — a Steve-Jobs-grounded design and craft discipline for a project's whole lifecycle.
- **[`andon`](https://github.com/Anselmoo/werkstoff/blob/main/plugins/andon/README.md)** — an evidence-grounded harden-and-advance loop: propose maximally, verify adversarially, never advance past an unproven wire.
- **[`cli-scaffold`](https://github.com/Anselmoo/werkstoff/blob/main/plugins/cli-scaffold/README.md)** — scaffolds production-grade CLIs across 12 languages against a frozen five-pillar doctrine.
- **[`codebase-consistency`](https://github.com/Anselmoo/werkstoff/blob/main/plugins/codebase-consistency/README.md)** — harmonizes undocumented pattern variants in an already-modern, live codebase.
- **[`takt`](https://github.com/Anselmoo/werkstoff/blob/main/plugins/takt/README.md)** — enforces declared beat order at the tool-call layer; inert until a repo declares its beats.
- **[`lehre`](https://github.com/Anselmoo/werkstoff/blob/main/plugins/lehre/README.md)** — researches a code style, pattern and architecture doctrine, then denies the write that would violate it.
