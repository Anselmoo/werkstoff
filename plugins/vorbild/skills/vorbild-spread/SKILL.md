---
name: vorbild-spread
description: "Use when the design direction is genuinely still open and several deliberately divergent idioms should be compared side by side, each presented in one fixed shell so the comparison is of systems rather than of presentations. Trigger on 'show me a few different directions', 'four properly different options, not four shades of the same one', 'we haven't picked a direction yet', 'vorbild spread'. Emits a forced-choice block and records the choice; until that record is answered the hook denies any write to tokens.json or out/. Not for variations inside one settled idiom — that is vorbild-echo."
argument-hint: "<system> [n]"
---

Produce *n* deliberately divergent idioms and make choosing between them unavoidable.

Use this early, when direction is open. If direction is settled and only expression is
open, this is the wrong skill — `vorbild-echo` is the right one, and running `spread`
there produces four answers to a question nobody asked.

## Divergent means divergent

The failure mode is *n* variations of one idea wearing different colours. Before
presenting, check each pair: if two proposals could be reconciled by changing one token,
they are one proposal. Replace one.

Make them differ on something structural — density, the role colour plays, whether the
system leads with type or with space, how much it asks the reader to infer. Each
proposal states the **premise** it is built on, in one sentence, and premises that are
not in genuine tension are not a spread.

## Fixed shell, bounded specimen zone

The comparison must be of systems, not of presentations. Four divergent idioms rendered
in four divergent shells cannot be compared at all — the reader is judging chrome.

So: **one fixed shell for every proposal**, with a bounded **specimen zone** per page
rendered in that proposal's own idiom. The shell keeps the comparison honest; the
specimen zone keeps each idiom judgeable on its own terms. Neither alone is enough — a
purely fixed shell hides the thing being chosen.

(`vorbild-echo` inherits the shell fully instead, because variations inside one idiom
stay comparable regardless.)

## The forced choice, and why it is enforced

Every spread ends with a block that names:

- the **decision** required, in one sentence
- what choosing each proposal **commits** to
- what choosing each proposal **forecloses**
- the **cost of not choosing**, stated concretely

Then write `<root>/system/spread-choice.json` with the proposal ids and `chosen` empty.

Until `chosen` is filled, the `PreToolUse` guard **denies** every write to
`<root>/system/tokens.json` and `<root>/out/`. That is deliberate: an n-proposal
portfolio with no forced choice is a procrastination machine, and a rule that depends on
a model choosing to honour it is not a rule. Record the choice together with what is
deliberately **not** adopted and why — that sentence is the part that survives into
`BRIEF.md`.

## Provenance still applies

A proposal is still derived. Each one cites the Design Cards behind it, and a proposal
resting only on grade-C evidence says so on its own page rather than borrowing the
confidence of the ones that do not.

If a proposal came from you rather than from a reference, **the page says so**.
Opinionated defaults presented as derived findings are the one thing that makes the whole
artefact untrustworthy — including the parts that were derived.
