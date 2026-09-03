---
task: "Check cross-forge CI parity"
category: ci-release
summary: "Compare two execution surfaces claiming to run 'the same checks' before trusting that both being green means they agree."
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
---

<RecipeHeader />

Two execution surfaces claiming to run "the same checks" drift silently, because nothing
compares them. The trap is that both surfaces are green and neither is running what the
documentation says it runs.

<RecipeBeats />
