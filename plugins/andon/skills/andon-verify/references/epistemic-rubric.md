# Strategy c: epistemic rubric

For wires whose contract is a *claim about the world* rather than a claim
about code behavior -- a documented assumption, a design rationale, a
"this approach is better because..." justification.

## The five criteria (check all five, independently)

1. **Falsifiability**: state the specific observation that would prove this
   claim wrong. If no such observation exists, the claim fails this
   criterion outright, regardless of how confidently it's stated.
2. **Generalization**: does the claim hold as an invariant across the
   contexts it's applied to, or only in the one case it was written for?
3. **Evidence-grounding**: does the cited evidence actually earn the
   strength of the claim being made? A single anecdote does not support
   "always" or "never."
4. **Honesty-of-framing**: does the stated confidence match the evidence?
   Flag both overclaiming ("proven" from one data point) and underclaiming
   (hedging away a claim the evidence actually supports well).
5. **Accessibility**: does a plain-language restatement of the claim still
   hold? If the claim only survives in jargon that obscures what's actually
   being asserted, that's a framing problem, not a pass.

Score each criterion pass/fail/neither independently -- do not average them
into one number. A claim can be falsifiable and well-evidenced but framed
dishonestly; that combination is still a `red` overall, because
honesty-of-framing failed.

## NO-PERSONA rule (binding, this strategy is where it's most tempting)

Grade every criterion anonymously, against the criterion's own definition
above -- never "this is the kind of claim [named expert] would endorse."
Borrowed authority from an identified individual (real, historical, or
fictional) is not evidence for any of the five criteria. If you catch
yourself about to write a name to justify a verdict, that is the signal to
find the actual checkable principle underneath and cite that instead. Run
`check-no-persona` on the drafted rubric text before finalizing.

## Verdict mapping

- All five pass -> `green`.
- Falsifiability or evidence-grounding fails -> `red` (the claim cannot be
  trusted as stated).
- Generalization, honesty-of-framing, or accessibility fails alone -> `unknown`
  (the claim may be true but is not currently provable/trustworthy as
  written; note which criterion failed and why in the evidence body).

## Detection Ladder

This strategy operates entirely at rung 0-1 conceptually (no code execution
involved) -- do not manufacture a rung-2+ "test" for a claim about the world;
that misapplies the ladder to a defect class it wasn't built for.
