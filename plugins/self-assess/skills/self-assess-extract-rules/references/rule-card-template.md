# Rule Card template

Every confirmed rule rendered into `BUSINESS_RULES.md` uses this exact
shape. This file is the schema only -- see `rule-card-examples.md` for
worked instances filled in with concrete values, and
`business-rules-report-sample.md` for what a full run's output file looks
like end to end.

## Schema

```
### {id}: {one-line plain-English name}
**Priority:** P0 | P1 | P2 | P3
**Confidence:** High | Medium | Low
**Citation:** `{file}:{line}`
**Specification:**
  Given {precondition}
  When  {trigger}
  Then  {outcome}
**Status:** confirmed
  [P0 rules only -- one line naming the panel outcome, e.g. "Two-judge
  panel confirmed: judge-a and judge-b both independently verified
  {file}:{line}."]
```

## Field rules (not optional)

- `{id}` matches the mining agent's own `id` field (`business-rules-miner`'s
  output contract) verbatim -- never renumbered when rendering the card.
- `**Specification:**` always renders `given`/`when`/`then` as three
  separate lines, in that order -- never collapsed into one paragraph, and
  never reordered.
- A P0 rule reaches `**Status:** confirmed` only when it carries
  `"panel_confirmed": true` -- `validate-artifact --kind
  business_rules_summary` (see `plugins/self-assess/scripts/lib/validators.py`)
  refuses any P0 rule missing that field or carrying anything else, so a P0
  rule can never be rendered as a confirmed card without having actually
  passed the two-judge panel.
- A P0 rule that did not pass the panel is never rendered as a card and
  never silently dropped -- it goes in the separate "Unconfirmed rules"
  section (see `business-rules-report-sample.md`) with its downgrade
  reason.
- P1-P3 rules have no panel requirement; `**Status:** confirmed` here means
  only "survived Step 2's citation verification" -- omit the bracketed
  panel-outcome line entirely for these, it applies to P0 only.

Note: unlike the JSON schema in `business-rules-miner.md`'s "Output
format" (which `self-assess-transform-brief`'s `flag-p0-blockers` actually
parses), this Markdown card format has no downstream parser today --
`BUSINESS_RULES.md` is a human-readable artifact only. The template exists
for rendering consistency, not because something reads it structurally.
