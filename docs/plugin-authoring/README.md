# Plugin & skill authoring standards

Read this before writing or editing a `SKILL.md` or agent file anywhere under
`plugins/`.

## Craft vs. content

This doc is opinionated about **how a skill/agent is built** (frontmatter shape,
progressive disclosure, writing voice, structure, wiring) and deliberately agnostic
about **what any given skill's output should contain** (the sections a report/rule-card
should have, the domain vocabulary — that's the author's per-plugin call, made with real
evidence, not a fixed template imposed from here).

That split, and most of the rules in [`references/craft-standards.md`](references/craft-standards.md),
are adapted from `Wirasm/prp`'s `prp-meta-skill` — a real, dispatchable skill for
authoring/refactoring skills that ships inside the `prp-core` plugin already installed in
this Claude Code session (pinned to commit `11427384c7609227f20c1d57e6c39de47ccf73c5` —
see [`references/output-shape-findings.md`](references/output-shape-findings.md) §2e for
how that identity was confirmed). werkstoff isn't shipping an equivalent dispatchable
skill of its own — this stays internal, project-scoped guidance for whoever works on
these six plugins, restructured to match `prp-meta-skill`'s anatomy (a lean entry point
+ `references/`) rather than one long flat file, because a flat file is exactly the
"prose instead of structure" pattern the craft rules below argue against.

## Resources

- [`references/craft-standards.md`](references/craft-standards.md) — the universal rules
  (skill types, anatomy, frontmatter spec, progressive disclosure, writing voice,
  no-duplication, structure-implies-a-maintainer, wiring references, portability), each
  checked against what werkstoff's six plugins actually do today, not assumed. Read this
  before starting any new skill/agent, or when something about an existing one feels off
  and you're not sure why.
- [`references/output-shape-findings.md`](references/output-shape-findings.md) — the
  content-side case study: a comparative audit against `anthropics/skills`,
  `anthropics/claude-plugins-official`, `obra/superpowers`, and `Wirasm/prp`, grounding
  one specific, now-largely-fixed finding (werkstoff describes output shape in prose
  instead of showing it) with real file citations on both sides. Read this when you want
  the evidence behind a craft-standards.md rule, or when deciding whether a *new*
  skill/agent needs a fenced output example.

## The headline finding

werkstoff's skills and agents are strong on **enforcement prose** (MUST/refuse language,
gates, validators) but were weak on **showing the shape of the output** — describing a
schema in a sentence instead of showing a worked, fenced instance. That gap is now closed
for every self-assess and confab auditor agent (see `output-shape-findings.md` §4.2) and
partially closed structurally for `self-assess-extract-rules` (a three-file
schema/example/report split, §4.6). What's still open, and the general rules to apply
when extending any of the six plugins, live in `craft-standards.md`.
