# Unresolved skills

Every `skill:` value used across the 25 rebuilt catalog entries was checked against a
real, existing definition before being written into frontmatter:

- werkstoff skills verified under `plugins/<plugin>/skills/<skill>/SKILL.md` and
  `plugins/<plugin>/agents/<agent>.md` in this repo.
- `superpowers:*` skills verified under
  `/Users/hahn/.claude/plugins/cache/claude-plugins-official/superpowers/*/skills/`.
- Official-plugin skills/agents (`pr-review-toolkit`, `code-modernization`,
  `frontend-design`, `plugin-dev`) verified under
  `/Users/hahn/.claude/plugins/cache/claude-plugins-official/<plugin>/`.

**No dead skills were found.** Every skill or agent id named in the old
`docs/orchestration/references/catalog.md` still exists at the path its plugin implies.
Nothing in this file was substituted or dropped for that reason.

## Note: beats dropped from the old catalog's tables, not from dead skills

Several old-catalog entries had table rows for a beat with no dedicated `#####` prompt
section to source a verbatim prompt from. An earlier pass over this catalog read the
frontmatter schema as requiring one literal prompt per beat, and left those beats out of
the rebuilt frontmatter rather than invent a prompt. **That was a bug in how the schema
was read, not a data problem** — `prompt` is optional on a beat; a beat with `skill:` and
`why:` but no `prompt:` is a valid, supported representation of a beat that the old
catalog's table names without giving it a dedicated worked example. None of these were
ever dropped because the skill was dead — all still exist and are real, usable beats.

All nine have since been restored as prompt-less beats directly in their recipes'
`beats:` list, in the table position the old catalog gave them, with the table's "Why
here, not later" cell copied in verbatim as `why:` and no `prompt:` key:

- **Scope an ambiguous task** — `compass:compass-negotiate-tradeoffs` restored (position
  3 of 4).
- **Scaffold a new project or CLI** — `cli-scaffold:cli-architecture` restored (position
  2 of 4).
- **Refactor for maintainability** — `superpowers:test-driven-development` (position 3 of
  5) and `codebase-consistency:equivalence-verifier` (position 5 of 5) restored.
- **Collapse duplication hand-synced across N sites** — `confab:confab-contract-drift`
  restored (position 3 of 4).
- **Migrate a return shape or type representation** — `andon:andon-verify` restored
  (position 4 of 4).
- **Whole-branch review without re-trusting the branch's own self-assessment** —
  `pr-review-toolkit:silent-failure-hunter`, `pr-review-toolkit:pr-test-analyzer`, and
  `confab:confab-contract-drift` restored (the old table's row 2 named the first two
  jointly with `pr-review-toolkit:code-reviewer` as one fan-out beat sharing one prompt
  and one why-cell; each now stands as its own beat, the two new ones carrying that same
  why-cell text verbatim and no prompt, since only `code-reviewer`'s row had a worked
  prompt to source one from).

A further three were initially left out on the reasoning that the source prose folds
them into another beat rather than giving them a standalone row. That distinction did not
survive checking: they are table rows without a dedicated prompt, which is precisely the
case the schema fix supports, and one of them (`superpowers:writing-plans`) is a
cross-ecosystem beat of exactly the kind this catalog exists to surface. They were
restored on the same rule, each with its own entry's "Why here, not later" cell verbatim:

- **Read-only design study with an evidence legend** — `compass:compass-summarize-trace`
- **A release path that has never succeeded** — `superpowers:writing-plans`
- **Same-stack version uplift** — `confab:confab-dependency-audit`

## Parity

Every beat named in the old catalog's tables is now represented in frontmatter:
**88 skill references in, 88 out, none missing.** A beat with `skill:` and `why:` but no
`prompt:` is valid and intended — it means the old catalog named the beat without giving
it a dedicated worked example, and inventing one would be fabrication, not restoration.
