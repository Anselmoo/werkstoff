---
task: "Do UI and design-system work"
category: surface
summary: "Convene the design council before any code, build against the settled design, then audit the built surface statically."
openingPrompt: "Design this screen from first principles before we write any markup -- convene the design council first, implement only the design it settles on, and once the markup exists, audit it statically for accessibility, semantic structure, and hardcoded design values against our shared token set."
external: ["claude-plugins-official"]
beats:
  - skill: "cupertino:cupertino-council"
    why: "Its own frontmatter: \"Always run before code, never after — retrofitting the council onto finished code defeats the purpose.\""
    prompt: "design this screen from first principles before we write any markup — I don't want something that just looks like every other AI-built page"
  - skill: "frontend-design:frontend-design"
    why: "Implementation after the principles are settled, not in place of settling them."
    prompt: "now implement the design we settled on"
  - skill: "self-assess:self-assess-ui-audit"
    why: "Accessibility, semantic markup, and hardcoded design values are only checkable once the markup exists."
    prompt: "audit the UI we just built for accessibility, semantic markup, and hardcoded design values — statically, don't run the app"
grounding: "the HTML surfaces this repo already ships — the andon board viewer built by `plugins/andon/scripts/build_board_html.py` and the branch-comparison viewer built by `plugins/compass/scripts/build_branch_comparison_html.py` — checked against the shared token set in `tools/design-tokens/tokens.css`."
dos:
  - "Convene the design council before any markup exists -- running it after defeats the purpose by its own stated rule."
  - "Implement only the design the council actually settled on, not an open brief."
  - "Audit the built UI statically for accessibility, semantic markup, and hardcoded values -- check it against the shared token set once real markup exists."
donts:
  - "Don't retrofit the design council onto a screen that's already built -- 'retrofitting the council onto finished code defeats the purpose' is the plugin's own stated rule."
  - "Don't skip straight to implementation on an interface that hasn't had a principled design pass yet."
  - "Don't audit for accessibility and hardcoded values before the markup exists -- there's nothing real to check yet."
---

# Do UI and design-system work

Design work has a hard ordering constraint that most other tasks do not: the principled
pass must precede the code, and the static audit must follow it. Running either in the
wrong order produces the appearance of both with the value of neither.
