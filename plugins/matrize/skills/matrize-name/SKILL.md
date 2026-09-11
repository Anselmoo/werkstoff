---
name: matrize-name
description: "Use to INTERPRET measured Design Cards into a named lexicon: every recurring element gets a name, a purpose, a rule and an anti-rule, written machine-addressably so matrize-dolmetsch can read it back. Trigger on 'name these elements', 'give every element a purpose and a rule', 'write the lexicon', 'matrize name'. Requires DECODE.md and refuses without it; a rule with no stated failure case is not emitted at all, and a rule whose purpose names neither a measured property nor a named principle is rejected as a copy."
---

Interpret what `decode` measured. This is the phase that makes claims, and it is
deliberately a different artefact written by a different agent, so a later reader can
always tell which sentences are measurements and which are judgements.

**Stop if `DECODE.md` is missing.** Naming without measurement is taste with a
vocabulary.

## Four fields, all mandatory

```
name        the term this system will use, and the only term it will use
purpose     why this element exists — what it is for, not what it looks like
rule        what must hold, stated so a person could check it
anti-rule   the failure case: what breaks when the rule is ignored
```

The anti-rule is the load-bearing half. A rule without a stated failure case is
decoration, and **is not emitted**. Working examples of the register to aim for:

- "Red stays the only dominant action colour per view, never two at once."
- "Script face exclusively for the slogan, never as a headline substitute."
- "Icons never stand alone."
- "Alert green never in the same view as beginner green."

Each names a specific thing that goes wrong. "Use red sparingly" does not, and would be
rejected.

## The test that stops this being a copying machine

> A rule whose `purpose` can name **neither** a measured property of the target
> (contrast, measure, touch-target size, a ratio from `DECODE.md`) **nor** a named design
> principle is a copy, not a rule.

`design-critic` rejects on exactly that test, and has standing to reject a card outright.
Draft every `purpose` against
`${CLAUDE_PLUGIN_ROOT}/references/principle-vocabulary.md`, which supplies the named
principles — and, because most of them carry a documented failure case, often supplies
the anti-rule too.

"The reference does it this way" is not a purpose. It is the absence of one.

## Use the controlled vocabulary, and its kind legend

`${CLAUDE_PLUGIN_ROOT}/references/vocabulary/` holds one file per dimension naming the terms
a design system actually uses — and, more usefully, the pairs people confuse. Adopt those
terms rather than coining near-synonyms: a lexicon that calls a gutter a gap has invented
a collision the vocabulary already warns about.

Each term carries a **kind**, and the kind decides where it belongs. This is a routing
rule, not a note:

| kind | where it goes |
|---|---|
| `token` | a stored value — `tokens.json` |
| `derived` | computed from tokens; **never stored separately** |
| `rule` | a constraint — a lexicon entry, **and it needs an anti-rule** |
| `property` | observed or measured; not stored at all |

So a `rule`-kind term with no anti-rule is not an incomplete entry, it is a
mis-classified one. And a `derived` or `property` term appearing in `tokens.json` is a
value that will drift from the thing it was derived from.

Two collisions the vocabulary names, worth checking every lexicon against: **margin** is
both a page concept and a box concept — if both appear, rename one — and **gutter** is a
property of the grid definition while **gap** is the CSS property realising it.

## Name in roles, not in appearances

A name that describes appearance dies the first time the appearance changes. `--ink`
survives a redesign; `--dark-grey` does not. Prefer the role the element plays: ink,
paper, hairline, dominant action, quiet action, alert.

Where a reference already names its own roles well, adopt the *pattern* of naming, never
the reference's brand-specific terms.

## Machine-addressable, not only prose

`dolmetsch` reads this file, so each entry needs a stable identifier and a predictable
shape — not a paragraph a reader can follow but a script cannot index. Keep one entry
per element, one heading per entry, and the four fields as labelled lines.

## Required coverage

Check the lexicon against these before declaring it done, and state any that are
genuinely absent rather than quietly omitting them:

1. **states** — hover and press are usually covered; **focus, disabled, loading and
   empty** are usually missing. Focus is not cosmetic: without it the system is unusable
   by keyboard
2. **contrast** — computed with `scripts/contrast.py`, never asserted
3. **motion** — duration, easing, distance, staggering, each with its anti-rule
4. **inverse / dark as a named mode**, with which role takes which value in which mode
5. **content rules** — character budgets per slot, tone, orthographic conventions
6. **provenance** — every entry cites the Design Card it came from

## Write LEXIKON.md

This skill writes the file; agents return structured entries. Lead with an index of
names, then the entries, then an **"Open"** section for every element that could not be
named because its evidence was direction-only.

## Resources

- `references/principle-vocabulary.md` — the named principles a `purpose` may cite, and
  the anti-copying test. Mandatory read before drafting any entry.
- `references/design-card-schema.md` — what the cards being interpreted look like.
- `references/vocabulary/*.md` — the controlled vocabulary and its kind legend, which
  routes every term to tokens, the lexicon, or neither. Mandatory read before naming.
