---
layout: home

hero:
  name: werkstoff
  text: A workshop of Claude Code plugins
  tagline: Twelve plugins that each catch one distinct failure mode, and a catalog of what to say to reach them at the moment they still help.
  image:
    src: /logo.svg
    alt: werkstoff
  actions:
    - theme: brand
      text: Get started
      link: /start/
    - theme: alt
      text: Prompt catalog
      link: /catalog/
    - theme: alt
      text: Plugins
      link: /plugins/
    - theme: alt
      text: Orchestration overview
      link: /orchestration/
    - theme: alt
      text: View on GitHub
      link: https://github.com/Anselmoo/werkstoff

features:
  - title: Indexed by task, not by plugin
    details: 38 development tasks, each broken into beats naming the skill that fires there and why it belongs there rather than later. 102 copy-paste prompts.
    link: /catalog/
    linkText: Open the catalog
  - title: Every prompt each plugin answers
    details: The example prompts from all twelve plugin READMEs, collected on one page and generated from the READMEs themselves so the list cannot drift out of date.
    link: /prompt-index
    linkText: Browse by plugin
  - title: Which pipeline owns the task
    details: Four pipelines compete rather than compose; two of them even rhyme through the same seven-phase skeleton. The routing table names which one owns a given task shape, and which to leave alone.
    link: /orchestration/references/routing
    linkText: Read the routing table
  - title: What happens when they share a session
    details: Nine plugins register a PreToolUse hook, two diff baselines can disagree, and two agents can collide on a name. The hazards, with their inert conditions and escape hatches.
    link: /orchestration/references/hazards
    linkText: Read the hazards
---

Twelve plugins, one job each — see [the plugin list](/plugins/) for what each one catches.
