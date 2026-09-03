---
task: "Check cross-forge CI parity"
category: ci-release
summary: "Compare two execution surfaces claiming to run 'the same checks' before trusting that both being green means they agree."
openingPrompt: "We claim two CI surfaces run the same checks -- audit both configurations for drift first, map every check to the surface that actually defines it so we can see what's missing where, and check whether our CI documentation still matches what the workflows actually do."
external: []
beats:
  - skill: "self-assess:self-assess-ci-topology"
    why: "Drift against CI documentation is precisely this skill's declared scope."
    prompt: "audit our remotes and CI configuration for redundancy and drift — I want to know whether the surfaces actually run the same checks"
  - skill: "compass:compass-map-relationships"
    why: "Parity is a multi-hop claim across files; it needs a traversable index, not a reading."
    prompt: "map every check we run to the surface that defines it, and show me which surface is missing which check"
  - skill: "self-assess:self-assess-docs-drift"
    why: "Documentation drift is what let the surfaces diverge unnoticed in the first place."
    prompt: "check whether our CI documentation still matches what the workflows actually do"
grounding: "this repo has two check surfaces and they are not aligned. `.pre-commit-config.yaml` runs three `rrt` hooks; `.github/workflows/plugin-checks.yml` runs pre-commit plus five further steps. Action pins drift across workflows too — `actions/checkout@v4` and `actions/setup-python@v5` in `plugin-checks.yml` against `actions/checkout@v7` and `actions/setup-python@v6` in `cicd.yml` and `auto-version-bump.yml`."
dos:
  - "Audit both CI surfaces for redundancy and drift before trusting that both being green means they agree."
  - "Map every check to the surface that defines it -- parity is a multi-hop claim and needs a traversable index, not a reading."
  - "Check the CI documentation against what the workflows actually do -- documentation drift is what let the surfaces diverge unnoticed."
donts:
  - "Don't assume two green CI surfaces are running the same checks -- this repo already has two that aren't aligned."
  - "Don't read parity off the workflow files alone -- it's a multi-hop claim that needs an index, not a skim."
  - "Don't trust CI documentation as current -- it's exactly what let the surfaces drift apart unnoticed in the first place."
---

<RecipeHeader />

Two execution surfaces claiming to run "the same checks" drift silently, because nothing
compares them. The trap is that both surfaces are green and neither is running what the
documentation says it runs.

<RecipeBeats />
