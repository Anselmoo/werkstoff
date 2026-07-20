---
enabled: true
house_rules_path: .claude/house-rules.md
output_dir: analysis/self-assess
languages: []
skip_verification: false
lint_max_rules: 12
transform:
  mode: plan
  authorized_phases: []
  require_clean_tree: true
idiom_fix:
  mode: propose
---

# self-assess configuration

Copy this file to `.claude/self-assess.local.md` in the repo you're
assessing, then edit or delete fields you want to override. Everything
shown here is already the default — delete a line to fall back to it,
or delete the whole file to use every default.

Remember to add `.claude/*.local.md` to this repo's `.gitignore`; this
file is per-project, user-managed, and not meant to be committed.

**The `transform` block is a deliberate authorization gate, not an
ordinary preference.** Leave `mode: plan` unless you specifically want
`self-assess-transform-execute` to be able to apply a Merge/Split/
layering-violation-fix phase from a `MODERNIZATION_BRIEF.md` — and even
then, list only the exact phase number(s) you've reviewed and authorized
in `authorized_phases`, never a blanket "all phases" entry. Re-confirm
this list whenever the brief regenerates; phase numbers can shift.

**The `idiom_fix` block is the same kind of gate, for a lower-blast-radius
case.** Leave `mode: propose` unless you specifically want
`self-assess-idiom-fix` to apply code-idiom's `modernization`-category
findings (mechanical, single-location rewrites like `Optional[X]` to
`X | None`) — it never touches `smell`-category findings either way, and
every fix it does apply still gets an explicit `andon-verify` hand-off
before anyone should trust it.
