---
enabled: true
house_rules_path: .claude/house-rules.md
output_dir: analysis/andon
ledger_dir: analysis/andon/ledger
authorization_level: local+reversible
skip_verification: false
lint_max_rules: 12
---

# andon configuration

Copy this file to `.claude/andon.local.md` in the repo you're hardening,
then edit or delete fields you want to override. Everything shown here
is already the default — delete a line to fall back to it, or delete
the whole file to use every default.

Remember to add `.claude/*.local.md` to this repo's `.gitignore`; this
file is per-project, user-managed, and not meant to be committed.
