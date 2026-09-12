# The vocabulary, and how it is enforced

Six files beside this one name what a design system is made of: one per dimension
(`color-system`, `grid-and-spacing`, `icon-system`, `motion`, `typography`) plus the
cross-cutting `visual-asset-taxonomy`. They are the domain layer, authored by hand.

They are not advice. `scripts/vocabulary.py` compiles them into a term registry, and
`scripts/validate_tokens.py` and `hooks/matrize_guard.py` enforce what the registry says.
A token that names no concept, names an unknown one, or claims a kind the vocabulary
contradicts does not get written.

This file carries the two things the six files do not state in a machine-readable place:
the canonical **kind legend**, and the **grade ceilings**.

## The kind legend

Every term in a dimension file carries a kind, and the kind decides where the term may
live. `grid-and-spacing.md` states this legend inline; the copy below is canonical, and
`vocabulary.py` fails with `VOCAB-LEGEND-DRIFT` if the two disagree.

| Kind | Meaning |
|---|---|
| `token` | A stored value. Belongs in `tokens.json`. |
| `derived` | Computed from tokens. Never stored separately. |
| `rule` | A constraint on use. Belongs in the lexicon with an anti-rule. |
| `property` | Something you observe or measure, not something you store. |

Two compound spellings appear in the term tables and normalise as follows. The map is
declared, never matched by substring — `derived from token` contains the word `token`, and
a containment test would file it under exactly the wrong kind.

| As written | Normalises to |
|---|---|
| `derived from token` | `derived` |
| `token (a text style)` | `token` |

## Grade ceilings — written, never inferred

Each dimension file ends with **Decoding notes**: what that dimension yields from a
reference, and at what reliability. Some of those notes are hard caps — a term that cannot
honestly be graded above a stated letter no matter how confident the decoder feels.

Binding a prose bullet to a term by matching text against 223 names would produce a
confident wrong ceiling. That is the same unsound move as reconstructing a provenance edge
by matching values, which invariant I8 already rejects: a rule that is confidently wrong
about what a source can support is worse than no rule.

So the binding is written here and *checked* against the bullets. `vocabulary.py` verifies
that every `term` below exists in the registry and that every quoted fragment still appears
verbatim in the named file; a ceiling whose bullet has been reworded is a finding, not a
silent pass.

`max` is a reliability letter, or `none` — meaning the value may not be set from a
reference at all and must be authored.

| Term | File | max | Quoted source bullet |
|---|---|---|---|
| Baseline grid | grid-and-spacing.md | C | Baseline grid — grade C at best |
| Keyline shapes | icon-system.md | C | Keyline shapes — grade C, and rarely worth the attempt |
| Growth rule | icon-system.md | none | Growth rule — never recoverable |
| Spring | motion.md | C | Spring parameters — grade C or absent |
| Stagger / cascade | motion.md | C | Stagger increment — grade C |

## Mandatory coverage

`visual-asset-taxonomy.md` names three classes missing from almost every design system and
almost always needed. Their absence is reported by `V-COVERAGE-MANDATORY`. The spellings
below are the taxonomy's own class names, not the prose ones from its closing paragraph --
`vocabulary.py` refuses a mandatory entry that binds to no class, which is how the first
draft of this table ("Empty state") was caught.

| Class |
|---|
| Empty state illustration |
| Error state illustration |
| Open Graph image |

## Extending the vocabulary

A project may genuinely need a concept none of the six files names. That is allowed, and it
is not silent: the token carries `vocab.extends` (why the vocabulary has no term) and
`vocab.declaredBy` (the Design Card that decided it). `matrize-status` reports the declared
extensions, which are the vocabulary's own backlog.

An unknown term *without* that record is a blocker. The registry stays authoritative, and
the cost of stepping outside it is one sentence of justification.
