---
name: matrize-retrofit
description: "Use to lift an existing project's ad-hoc CSS into the design-system taxonomy WITHOUT changing anything visually — naming what is already there, recording where each value came from, and proving zero visual diff rather than asserting it. Trigger on 'organise this project's scattered CSS', 'name what we already have', 'same pixels, just systematised', 'matrize retrofit'. Never redesigns: a value that would change is surfaced as a question, not adopted. Not for deriving a new system from external exemplars (matrize-decode) and not for auditing a repo for convention divergence, which is codebase-consistency's job."
argument-hint: "<system>"
---

Name what already exists. Change nothing about how it looks.

This is the method that hardens the taxonomy against real material before the taxonomy
has to generate anything new — and it is the one `spread` gets wrong by redesigning when
it should be naming.

## The discipline

> If the pixels move, the retrofit failed. A value you want to change is a **finding**,
> not a change.

A retrofit that "tidied up while it was in there" has destroyed the only equivalence
proof available and cannot be distinguished from a redesign afterwards.

## Step 1 — inventory what is declared

Read the existing CSS, token file, theme config or framework config. For every declared
value record: the value, every place it is used, and whether the same role already has
more than one value.

Multiple values for one role is the normal finding, not an error. Record all of them.

## Step 2 — map onto the taxonomy

For each declared value, assign the role it actually plays and the lexicon name for that
role. Three outcomes, and each is a legitimate result:

- **Maps cleanly** — one value, one role, one name.
- **Maps to several** — one role carries two or more values. Record every variant with
  its call sites. Do **not** pick a winner here; that is a decision for the human, and
  `brief` is where it gets made.
- **Does not map** — the value plays a role the taxonomy has no name for. That is a gap
  in the taxonomy, and saying so is the point of running retrofit first.

## Step 3 — emit the neutral source

Write `<root>/system/tokens.json` in DTCG form, carrying provenance in `$extensions`:
for each token, the file and selector it was lifted from, its reliability grade (here
usually **A** — it is the project's own source), and its rights grade (**R1**, the user's
own material).

## Step 4 — prove it, do not claim it

Regenerate the original format with `emit --target <the original format>` and compare:

1. **Textual** — normalised diff of the regenerated file against the original. Declared
   values must be identical; ordering and formatting may differ.
2. **Visual** — render a page that exercises the tokens against both, screenshot both at
   the same width, and compare. This is the strongest equivalence proof available and it
   should be mechanised rather than eyeballed.

Report the result as a measurement. "Zero visual diff" is a claim that must be backed by
the comparison actually having run — if it did not run, say that instead.

## Step 5 — report what is now decidable

End with three lists:

- **named** — roles that mapped cleanly
- **contested** — roles carrying more than one value, each with its call sites, for
  `brief` to settle
- **unnamed** — values the taxonomy could not express, which is a taxonomy finding

## What this is not

Not a drift audit. It never asks whether the code still matches a system — matrize
creates the system, `codebase-consistency` guards it. And it never scans for convention
divergence across a repo; the moment that is the question, `/consistency-scan` owns it.
