# Cannibalize Yourself Before Someone Else Does

> "If we don't cannibalize ourselves, someone else will."

The most well-documented instance of this at Apple is the iPhone killing the
iPod. The iPod was Apple's most successful product line at the time the
iPhone shipped, generating a large and reliable share of the company's
revenue. The iPhone included, as one of its core functions, a full iPod —
and within a few years had substantially cannibalized iPod sales. Apple
built the product that made its own most successful product obsolete,
deliberately, before a competitor (most plausibly a phone maker who added
music playback) could do it to them from outside.

## Why this is a distinct technique from cupertino-longevity, not a
restatement of it

Both this technique and `cupertino-longevity` can produce the sentence
"we're replacing this." That surface similarity is exactly why this
document exists: the two are opposite verdicts wearing the same words, and
collapsing them is the single most likely misapplication of either
technique.

**The exact distinguishing test:**

- **Forced by decaying architecture = Vista Trap** (bad, avoid) — this is
  `cupertino-longevity`'s whole subject. The replacement is happening
  *because* an earlier design decision became a load-bearing wall that
  can no longer move, and the team has no real choice left but to
  rewrite. The tell: if you ask "could we have kept incrementally
  improving the old thing instead?" and the honest answer is "no, the
  architecture won't allow it anymore," that is a Vista Trap, not
  cannibalization — see `longevity.md` for the full diagnostic.
- **Chosen because you can build the successor better than a competitor
  will = cannibalization** (good, deliberate) — this technique's subject.
  The team *could* keep shipping the old thing largely as-is, profitably,
  for a good while longer. They choose not to, because they believe they
  can build a successor that makes the old thing obsolete better and
  sooner than a competitor could, and would rather be the one who does it.
  The tell: if you ask the same question — "could we have kept
  incrementally improving the old thing instead?" — and the honest answer
  is "yes, easily, we're choosing not to," that is cannibalization.

Same surface symptom ("we're replacing this"), opposite motive. Getting
this test right matters because the two call for opposite responses: a
Vista Trap is a failure to be prevented earlier next time (apply the
Rosetta Roadmap, don't repeat the pattern); a deliberate cannibalization is
a success to be repeated, on a cadence, before a competitor forces it
instead.

## Applying it in software work

This runs **post-ship, on an ongoing cadence** — not as a one-time
decision, and never automatically triggered per-PR or per-release (see the
frontmatter note below on why this is user-invoked only).

1. **Name the current most-successful, most-load-bearing thing** — the
   product, feature, API, or workflow that currently generates the most
   value/revenue/usage, and that the team would be most reluctant to touch.
2. **Ask honestly whether it could keep improving incrementally**, using
   the distinguishing test above. If the honest answer is "no, the
   architecture won't allow it," stop — that's `cupertino-longevity`'s
   diagnostic, not this one; go run that instead.
3. **If the honest answer is "yes, it could keep improving" — ask whether a
   competitor building the obvious successor is a real, credible threat**,
   not a hypothetical one. Cannibalization only makes sense as a deliberate
   choice when the alternative (a competitor doing it first) is plausible;
   manufacturing a fake threat to justify a rewrite is misapplying this
   technique in the other direction.
4. **If the threat is real: decide, explicitly, whether the team builds the
   successor itself.** Name what's being deliberately made obsolete, and
   accept the short-term cost (cannibalized revenue/usage/adoption of the
   current thing) as the price of not losing the long-term position to
   someone else.
5. **State the decision out loud**, the same way Apple's iPhone-vs-iPod
   decision was ultimately a leadership call, not an emergent accident —
   cannibalization done well is chosen and owned, not discovered after the
   fact.

## User-invoked only — this is not a per-PR check

Unlike most of `cupertino`'s other techniques, `cupertino-cannibalize` must
**never** be triggered automatically as part of routine work — not on every
PR, not on every release, not as a standing item in `cupertino-review`'s
pipeline the way `cupertino-backwards` through `cupertino-reveal` run.
Deciding to cannibalize your own most successful thing is a leadership-level
call with real, immediate costs (see the distinguishing test above); running
this analysis reflexively on every change would produce constant unwarranted
pressure to replace things that are working fine and facing no real
competitive threat. `cupertino-review`'s pipeline includes this technique
only as a cadence-triggered, explicitly user-invoked final step — see its
own `SKILL.md` frontmatter and pipeline description for the exact phrasing
that keeps this from firing automatically.

## Where this sits in the cupertino lifecycle

Post-ship, ongoing cadence, user-invoked only — the one technique in this
plugin that is not part of the automatic per-project pipeline
`cupertino-review` otherwise runs start to finish.
