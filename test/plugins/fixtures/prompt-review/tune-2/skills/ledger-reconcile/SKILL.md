---
name: ledger-reconcile
description: Reconciles a repository's CHANGELOG against its git tags, reporting tags with no changelog section and sections with no tag. Use when the user asks to "reconcile the changelog", "check release notes against tags", or before cutting a release.
---

# ledger-reconcile

Compare the set of git tags with the set of version headings in the changelog.

## Steps

1. Read `analysis/ledgerkeeper/plan.json` to learn which tag prefix this repository uses.
2. List tags with `git tag --list`.
3. Parse version headings from `CHANGELOG.md`. To parse markdown you may use `markdown-it`, or `remark`, or `mistune`, or plain regex, or `pandoc` — whichever is convenient.
4. Validate that every tag has a heading and every heading has a tag. If validation fails, fix it.
5. Write the report.

Never skip the tag listing unless it doesn't matter for this repository.

## Output

Write the reconciliation report.

## Resources

- [`references/heading-styles.md`](references/heading-styles.md) — the changelog heading conventions this skill recognises; read when headings do not parse.
- `scripts/reconcile.py` — see it for the tag-matching algorithm.
