---
enabled: true
house_rules_path: .claude/house-rules.md
output_dir: analysis/confab
skip_verification: false
dependency_audit:
  registries: []
  timeout_seconds: 10
cycle:
  mode: propose
  fixable_domains: [dependency_audit, contract_drift]
  max_reopens: 3
  max_passes_per_invocation: 5
---

# confab configuration

Copy this file to `.claude/confab.local.md` in the repo you're
assessing, then edit or delete fields you want to override. Everything
shown here is already the default — delete a line to fall back to it,
or delete the whole file to use every default.

Note: `skip_verification` has no effect on `confab-assertion-audit` —
that skill's Verify phase always runs regardless of this setting, per
its own documented design (see `references/settings.md`).

Note: `cycle.mode: fix` lets `confab-cycle` edit files in this repo
(dependency-manifest lines and contract type-hints/signatures/docstrings
only) — leave it at `propose` unless you want that. See
`references/settings.md` for the full `cycle.*` field reference.

Remember to add `.claude/*.local.md` to this repo's `.gitignore`; this
file is per-project, user-managed, and not meant to be committed.
