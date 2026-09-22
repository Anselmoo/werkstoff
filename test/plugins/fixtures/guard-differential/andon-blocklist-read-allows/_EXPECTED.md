# andon — a block-list record is finally readable (old=deny, new=allow)

## The scenario

A gap whose state lives **only** in a YAML block list — no first-class keys at all:

    tags:
      - kind:wire
      - status:open
      - blast-radius:local+reversible

Everything the hook needs is present. It should not halt.

## Why this pair is the right pair

The old `frontmatter()` was one line-regex matching `key: value`. A block list gave `tags` an
**empty string**: the `tags:` line matched with an empty capture, and the `  - ` lines matched
nothing and were dropped. So `tag_value` found no `blast_radius`, and the hook halted on
required-field integrity (contract §9.2) — *"carries no blast-radius value… never inferred"* —
for a record that carries it plainly.

Note the direction, which is the opposite of what it first looks like. The unreadable record
did not sail through; it **denied**, because an unreadable value is indistinguishable from an
absent one and absent is correctly a stop. So the defect here is over-denial, and the fix is
`deny → allow`. (I wrote this pair the other way round first, and the runner refused it —
`old expected allow, got deny`.)

That form is not exotic: it is what `andon_core.dump_frontmatter` writes, what
`okf-ledger-schema.md:59-72` documents as canonical, and what every record in
`scripts/fixtures/sample_ledger/` uses. The hook could not read the shape its own plugin
produces, and no test noticed because all 11 fixture constants in `test_andon_enforce.py` are
inline-JSON.

## Its partner

`andon-blocklist-missing-blast-halts` drops the blast-radius line. Deny before, deny after —
because now the value really is absent, and absent is still never inferred. It separates
"block lists are read" from "block-list records are waved through", which is the failure mode
a careless fix would produce and which this case alone could not see.
