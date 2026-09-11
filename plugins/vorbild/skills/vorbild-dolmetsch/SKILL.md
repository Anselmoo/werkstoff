---
name: vorbild-dolmetsch
description: "Use to translate between vague design instruction and the precise terms of a derived system, in both directions — 'make it airier' into named tokens and numbers on the way in, and named tokens back into plain language on the way out. Trigger on 'make it airier', 'what does that mean in actual numbers', 'say that in plain English', 'vorbild dolmetsch'. Cross-cutting rather than a pipeline phase: callable from any point, it reads LEXIKON.md as its only dictionary and says plainly when a term is missing rather than guessing at one."
---

Translate. Do not invent vocabulary.

A *Dolmetscher* interprets speech in the moment, in both directions. This skill does the
same between two registers that constantly talk past each other: the one a stakeholder
uses ("cleaner", "more premium", "airier") and the one the system uses (named roles,
tokens, ratios).

## `LEXIKON.md` is the only dictionary

There is no separate knowledge base, and that is deliberate. If translation had its own
vocabulary, the system would have two, and they would drift — which is the failure the
lexicon exists to prevent.

## Vague → precise, on the way in

Resolve the instruction into named elements and concrete values:

> "make it airier" → line-height `1.6 → 1.75`, spacing step `+1`, measure capped at `65ch`

Always name the **elements** being changed, not just the numbers — the elements are what
the system can reason about later, and a bare set of numbers is a patch, not a decision.
Where an instruction touches something with an anti-rule, quote the anti-rule back: the
fastest way to settle "more emphasis" is usually the rule that says only one dominant
action colour per view.

## Precise → plain, on the way out

The same job in reverse, and just as load-bearing: a stakeholder who cannot read the
system cannot approve it. Render token names and ratios into a sentence a
non-technical decision-maker can act on, without flattening the reason into "it looks
better".

## When a term is missing, say so

> If a term is not in `LEXIKON.md`, **say that it is missing**. Do not guess, and do not
> invent a plausible mapping.

A guessed mapping is indistinguishable from a real one once it has been acted on, and
it quietly creates a term the system never agreed to. The honest response names what
*is* in the lexicon nearby and asks which was meant — or reports that the concept has no
name yet, which is a finding for `vorbild-name`.

An empty or absent lexicon is therefore a **correct** state for this skill to be in, not
an error: it reports that there is nothing to translate against yet. That is why it can
be built after `vorbild-retrofit`, which produces the first real lexicon, at no cost.

## Record what the translation settled

When a translation resolves a recurring ambiguity — the third time "cleaner" turns out
to mean "fewer competing weights" — that belongs in `LEXIKON.md` as a rule with its
anti-rule, not in this session's scrollback. Say so, and hand it to `vorbild-name`.
