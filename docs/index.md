---
layout: home

hero:
  name: werkstoff
  text: A workshop of Claude Code plugins
  tagline: Eight plugins that each catch one distinct failure mode, and a catalog of what to say to reach them at the moment they still help.
  actions:
    - theme: brand
      text: Extended prompt catalog
      link: /orchestration/references/catalog
    - theme: alt
      text: Orchestration overview
      link: /orchestration/
    - theme: alt
      text: View on GitHub
      link: https://github.com/Anselmoo/werkstoff

features:
  - title: Indexed by task, not by plugin
    details: Twenty-five development tasks, each broken into beats naming the skill that fires there and why it belongs there rather than later. Seventy-six copy-paste prompts.
    link: /orchestration/references/catalog
    linkText: Open the catalog
  - title: Every prompt each plugin answers
    details: The example prompts from all eight plugin READMEs, collected on one page and generated from the READMEs themselves so the list cannot drift out of date.
    link: /prompt-index
    linkText: Browse by plugin
  - title: Which pipeline owns the task
    details: Four pipelines share the same eight-step skeleton and compete rather than compose. The routing table names which one owns a given task shape, and which to leave alone.
    link: /orchestration/references/routing
    linkText: Read the routing table
  - title: What happens when they share a session
    details: Five plugins register a PreToolUse hook, two diff baselines can disagree, and two agents can collide on a name. The hazards, with their inert conditions and escape hatches.
    link: /orchestration/references/composition
    linkText: Read the hazards
---
