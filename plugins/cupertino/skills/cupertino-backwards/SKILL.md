---
name: cupertino-backwards
description: >
  Starts from the customer's actual experience and works backwards to the
  technology, before any architecture or design work begins — grounded in
  Steve Jobs' 1997 internal Apple talk ("start with the customer experience
  and work backwards to the technology"), with a caveat separating empathy
  for the customer's problem from literally transcribing their feature
  request. Use FIRST, before cupertino-focus or any other cupertino
  technique, whenever a feature or project is being scoped — "what should we
  build for this", "here's what the user asked for", "start from the user
  experience", "work backwards from the customer", "what's the actual problem
  here", or the start of any greenfield design conversation. Also trigger
  when a stakeholder's literal request is about to be built as-is without
  separating it from the underlying problem. Do not use mid-build or post-
  ship — this is a pre-architecture gate, not a retrospective review.
---

Start with the customer experience, work backwards to the technology — and
never confuse that with taking a feature request literally. Full grounding,
the historical 1997 talk, and the caveat resolution live in
`../../references/backwards.md`; read it before applying this technique,
especially the "caveat that keeps this from being self-contradictory"
section if the customer's stated request and their underlying problem
haven't yet been separated.

## When to use

First technique in the `cupertino-review` lifecycle — runs before any
architecture or design work starts on a new feature or project. If the
conversation has already moved into "which framework" or "what's the data
model," this technique runs too late to do its job; the customer-experience
statement it produces should already be settled by then.

## Process

1. **State the customer experience in one sentence with zero technology
   nouns.** No database, framework, API shape, or widget name. If any
   sneak in, the sentence has already smuggled in a technology answer —
   rewrite until it describes only what the person is trying to accomplish
   and what "good" feels like when they get there.
2. **Write the stated request and the underlying problem side by side,
   explicitly.** These are frequently different. A request for "a button
   that exports to CSV" might really be "I need to hand this data to
   someone in a tool I don't control" — and the eventual answer may not be
   CSV at all. See `../../references/backwards.md` for the full worked
   reasoning on why this split matters and how Jobs' "people don't know
   what they want until you show them" quote resolves against it rather
   than contradicting it.
3. **Work backwards from the experience to the technology**, willing for
   the technology answer to differ from the literal original request.
   Skipping this step — building exactly what was asked for without doing
   this work — is the backwards-development pattern the source talk was
   diagnosing.
4. **Flag when the experience statement and the literal request are
   identical.** That's not automatically wrong, but it's a signal to check
   one level deeper before treating the request as fully settled.

## Output

- The one-sentence customer-experience statement (no technology nouns).
- The stated request vs. the underlying problem, side by side.
- The technology direction chosen, with one sentence on how it serves the
  experience statement — not just "how it fulfills the request."
- Any point where the technology direction and the experience statement
  might drift apart later, named explicitly rather than left implicit.

## What this is not

Not a mandate to override what users explicitly ask for — their diagnosis
of the problem is usually the most valuable input in the room. Not a
license to substitute personal taste for customer empathy. See
`../../references/backwards.md`'s "What this technique is not" section for
the full statement.

## Relationship to other cupertino skills

Downstream of nothing — this is the pipeline's entry point. Everything that
follows in `cupertino-review` (`cupertino-focus`'s scoping,
`cupertino-longevity`/`cupertino-integrate`'s architecture calls,
`cupertino-council`'s UI decisions) inherits whatever customer-experience
statement this step produces.
