---
name: vorbild-brief
description: "Use to synthesise a design-system derivation into the approval artefact a human signs: target taxonomy, chosen direction, what is deliberately NOT adopted and why, and falsification criteria stating what would show the system does not hold. Trigger on 'write the design brief', 'what are we actually proposing', 'put this in front of the decision-maker', 'vorbild brief'. Stops outright if any discovery artefact is missing, warns when the state-of-the-art survey is past its expiry, and writes nothing further until the approval block is signed — no objection is not approval."
argument-hint: "<system> [direction]"
---

Synthesise discovery into a document a human can approve or reject. This is the
human-in-the-loop gate, and it is the reason an n-proposal portfolio is a decision aid
rather than a procrastination machine.

## Hard input gate

Read `<root>/system/DECODE.md` and `<root>/system/LEXIKON.md` first. **If either is
missing, say so and stop.** They come from `vorbild-decode` and `vorbild-name`; run
those. Do not synthesise around an absent input — a brief assembled from a missing
measurement is the one artefact nobody can audit later.

If `<root>/system/STATE-OF-THE-ART.md` exists and is past its stated expiry, **warn and
name the claim that forced it**. The style of a design system does not go stale; its
delivery chain does.

## What the brief contains

1. **Target taxonomy** — the named elements this system will carry, from `LEXIKON.md`.
2. **Chosen direction**, stated in one paragraph a non-technical reader can hold.
3. **What is deliberately not adopted, and why.** This section is not optional and not
   decorative. A brief that only says yes has recorded no decision.
4. **Falsification criteria** — what would show this system does not hold. Write these
   as things that could actually be observed: "a view needs two dominant action colours
   and neither can be demoted", "the spacing scale cannot express the densest table we
   ship". A criterion nobody could ever observe is not a criterion.
5. **Open questions**, carried verbatim from every grade-C-only finding and every
   unanswered `preflight` question.
6. **Coverage** — state explicitly which of the six required areas (states, contrast,
   motion, inverse mode, content rules, provenance) the system covers and which it does
   not. A system missing any of them is incomplete, and this is where that is said.

## Phase entry criteria are gates, not aspirations

The three build methods — `echo`, `spread`, `retrofit` — read this brief and treat its
entry criteria as binding. So write them as **checkable preconditions**: "`tokens.json`
validates against the DTCG profile", "every colour role has a computed contrast figure",
not "colours are finalised".

Tell the approver plainly that they steer execution by editing this file. **An edited
entry criterion is honoured; a note in a chat is not.**

## The approval block

End with it, and enter plan mode if the session supports it:

```
This is a discussion basis, not a finished rulebook.

Decision-maker: ______________________
Gate criteria:  feedback on <the specific things> before production
Approved by: ________________  Date: __________
Approval covers: <direction only> | <direction and taxonomy> | <the whole system>
```

Then **stop — write nothing further until the user explicitly approves.** "No objection"
is not approval. `vorbild-status` reads this block and reports whether it is signed.

## This brief is a hypothesis

Say so in the document. What the first real emit surfaces — a token the taxonomy cannot
express, a role that turns out to be two roles, a reference that contradicts another —
is *expected* to revise this brief. A regenerated brief after the first build is the
normal path, not a correction.

## Staleness

Compare modification times. If any input is newer than an existing `BRIEF.md`, the brief
is being justifiably regenerated. If the brief is newer than every input and it is being
re-run anyway, ask what changed. Either way, record the input timestamps in the header so
a reviewer can see what it was built from.
