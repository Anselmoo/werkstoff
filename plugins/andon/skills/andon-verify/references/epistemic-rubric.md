# Strategy c — Epistemic/claim wire: falsifiability, generalization, evidence-grounding

For wires that are a **claim**, not code — a design rationale, an
architecture statement, a "this generalizes" or "this approach is
honest" assertion that needs epistemic scrutiny rather than execution.
Extracted from the personal `solvay-council` skill, but **reshaped as an
anonymous rubric only** — this is not a named-persona council, and it
must never become one. See the NO-PERSONA RULE below.

## NO-PERSONA RULE (reiterated here, binding for this strategy specifically)

The source skill (`solvay-council`) convenes distinct named historical
scientists — Planck, Feynman, Curie, Popper, and others — each voice
carrying implicit authority from the real, identified individual it
represents. That mechanic is **not ported**. This strategy keeps only the
*underlying epistemic criteria* those voices tested for, stripped of any
named-persona framing:

- Every criterion below is evaluated by asking the question directly,
  never by invoking "what would [named scientist] say."
- Nothing in this strategy's output should read as an appeal to a named
  individual's authority. If a criterion needs a name at all, name the
  *criterion* (falsifiability, generalization, evidence-grounding), never
  a person.
- This is the one part of the plugin-wide NO-PERSONA RULE (see
  `andon-verify/SKILL.md`) that required active restructuring rather than
  just stating the rule — the source material's whole mechanic was
  named-voice-based, so this rewrite is deliberate, not an oversight.

## The rubric (anonymous, criterion-named)

| Criterion | Question | Fails when |
|---|---|---|
| **Falsifiability** | What observation would prove this claim wrong? | The claim is unfalsifiable, or vague enough to explain any outcome after the fact. |
| **Generalization** | What stays invariant — does this generalize past the one case it was checked on? | The claim is true only in the specific instance tested and is stated as if general. |
| **Evidence-grounding** | Does the evidence actually earn the claim, or does the claim outrun its measurement? | A claim is stated more strongly than the cited evidence supports. |
| **Honesty of framing** | Is the claim's own confidence stated accurately, or does the framing borrow credibility it hasn't earned (self-certification, appeal to authority, crowning language)? | The claim self-certifies ("proven", "definitively") without evidence proportional to that strength. |
| **Accessibility of the actual claim** | Stripped of jargon, what is this actually asserting — and does that plain-language version still hold up? | The claim only survives scrutiny while dressed in domain jargon that obscures what's actually being said. |

## Why these five (a citation trail, not a role call)

Each criterion traces to an established, independently-checkable
principle — cited the way you'd cite a theorem, not the way you'd quote
a person's opinion. That distinction is what actually keeps this inside
the NO-PERSONA RULE: a citation says "this idea exists, is on the
record, and says X — go verify it yourself"; a persona voice says
"trust this because someone respected would agree with it," which is
the exact appeal-to-authority this rubric exists to catch. Naming a
theorem after its discoverer (Noether's theorem, same as "the
Pythagorean theorem") is normal technical citation; simulating what
that person would say about *this* claim is not — the five entries
below are the former, never the latter.

| Criterion | Traces to | The actual idea |
|---|---|---|
| Falsifiability | Popper's falsifiability criterion | A claim only counts as a real, scientific claim if some observation could in principle prove it false; a claim compatible with every possible outcome isn't asserting anything. |
| Generalization | Noether's theorem | Every continuous symmetry of a system corresponds to a conserved quantity — asking "what stays invariant under a transformation" is structurally the same move as asking whether a claim holds across contexts, not just the one it was tested in. |
| Evidence-grounding | The evidentiary standard behind Curie's radioactivity measurements | Extraordinary claims were earned through repeated, quantitative measurement under difficult conditions, never asserted beyond what the data showed — the discipline of not letting the claim outrun the measurement. |
| Honesty of framing | Feynman's "you must not fool yourself — and you are the easiest person to fool" | Confidence should be reported as it actually is, not dressed up in self-certifying language ("proven," "definitively") that borrows credibility the evidence hasn't earned. |
| Accessibility | The plain-language discipline behind Hawking's and Lesch's science writing | If a claim only survives while wrapped in jargon, the plain-language version — stripped of domain vocabulary — is the real test of whether it still holds. |

None of this table is surfaced when the strategy actually runs — it
exists so this document is a real citation trail, not folklore. The
strategy's own output only ever names the *criterion* (falsifiability,
generalization, evidence-grounding, ...), never the theorem or the
person behind it.

## Workflow

1. **State the claim precisely** — the actual assertion on the table,
   not the wording around it (the wire's contract, restated as a single
   falsifiable sentence if possible).
2. **Audit each criterion** — one finding per criterion, specific to the
   claim (never "this is good" — name the specific sentence, number, or
   design choice that the finding is about).
3. **Resolve tensions** — when criteria conflict (e.g. accessibility vs.
   completeness), honesty and evidence-grounding outrank persuasiveness
   or narrative neatness; state the resolution and why.
4. **Verdict.** A claim that fails falsifiability or evidence-grounding
   is 🔴 regardless of how well the other criteria score — those two are
   load-bearing for whether the claim counts as evidence-grounded at
   all. A claim that passes all five, or whose only gaps are
   accessibility-only, is 🟢. Genuinely contested (evidence exists on
   both sides) → ⚪, not a forced verdict.

## Anti-fabrication boundary

This strategy **identifies** gaps — the missing evidence, the
unfalsifiable framing, the special case stated as general. It does
**not invent** data, citations, or results to fill a gap it names. When
evidence is missing, the honest output is "this claim is not yet earned
— here is what would earn it," never a fabricated earning.

## When NOT to reach for this strategy

If the claim is actually a numerical claim with a computable answer, use
strategy b instead — b is more specific and produces an actual number,
not a qualitative epistemic verdict. If the question is "would this
passing test actually catch a regression," that's strategy g, not this
one — g audits test strength, not claim honesty.
