---
task: "Decide an architecture that will not force a rewrite"
category: before-any-code
summary: "A fixed chain of declared-position beats -- cut the portfolio, check longevity, name the integration seam, then stress-test the decision -- each one only valid once its predecessor has already run."
external: ["claude-plugins-official"]
beats:
  - skill: "cupertino:cupertino-backwards"
    why: "Its own frontmatter states it directly: use FIRST, before cupertino-focus or any other cupertino technique -- a pre-architecture gate, run once no framework or database has been named yet."
    prompt: "before we pick any architecture or framework, work backwards from what this actually needs to do"
  - skill: "cupertino:cupertino-focus"
    why: "Use immediately after cupertino-backwards -- architecture must never be built to support an uncut portfolio of features."
  - skill: "cupertino:cupertino-longevity"
    why: "Run at architecture-decision time, together with cupertino-integrate -- the Vista-Trap check, catching a design that looks modern today and stale in two years."
  - skill: "cupertino:cupertino-integrate"
    why: "Own-vs-delegate, one named integration seam per invocation -- never issued as a blanket policy across the whole system."
  - skill: "code-modernization:architecture-critic"
    why: "Adversarial close: over-engineering and simpler alternatives, judged against the settled decision rather than against the enthusiasm that produced it."
    prompt: "review this architecture decision adversarially -- where is it over-engineered, and what's the simpler alternative we didn't take seriously?"
grounding: "This repo's own eight independent version groups in .rrt.toml, with deliberately no aggregate werkstoff version -- a real longevity/integrate decision (each plugin owns its own release seam) that no recipe currently shows anyone how to reach."
---

Each beat here is only valid once its predecessor has already run: cupertino-backwards
must precede any named framework, cupertino-focus must precede longevity and integrate,
and architecture-critic must close the chain rather than open it. Skipping ahead — naming
an integration seam before the portfolio is cut, or reviewing adversarially before a
decision exists to review — produces a verdict on the wrong artifact.
