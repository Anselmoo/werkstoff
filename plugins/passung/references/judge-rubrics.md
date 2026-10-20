# Judge rubrics

The rubrics passung's judges are held to. The contract they follow is
`judge-contract.md` (vendored beside this file): the judge reports a score and evidence per
criterion, and code (`decideVerdict` in the workflow) computes the outcome. Each rubric
below is copied into the workflow that uses it, with the same id, threshold and criteria.
Raise the `@N` here and in the workflow together on any change to a question or a
threshold, because a verdict is only comparable to verdicts from the same version.

Neither rubric has a calibration record. No sealed set has been measured for either, so
every verdict they produce says `calibrated: false`, and each run shows the user a sample
(`spotCheck`) to read.

## `passung-provenance@1`

Used by `workflows/canonize.js`. One judge per `derived-majority` Pattern Card. Item id:
the card's dimension, lower-cased. Threshold: **0.7** (the minimum criterion score).

| criterion | question |
|---|---|
| `basis-supports-winner` | Re-derive the frequency, maturity and recency weighing yourself: does it support this winner over the alternatives, or is the reasoning thinner than it sounds? |
| `form-faithful` | Does the stated canonicalForm match what the winning variant's cited sites contain, verbatim, not an idealized version of it? |

Outcome `pass` leaves the card `derived-majority`. A `fail` or an `abstain` (including a
judge that returned nothing) turns it into `needs-human-decision` with an open question
that quotes the failing criteria's evidence or the abstain reason. It is never canon.

This replaces a two-judge panel (a basis-soundness judge and a fidelity judge, both
required to agree). The two lenses are now two criteria of one judge call.

## `passung-equivalence@1`

Used by `workflows/verify.js`. One **blind** judge per module whose first verdict is
`PASS`: it is shown neither that verdict nor its reasoning, and runs the module's tests
itself. Item id: the unit name. Threshold: **0.7**.

| criterion | question |
|---|---|
| `changed-branches-covered` | Every branch the diff touches (error path, boundary condition, null case) is covered by a test that actually ran. |
| `docs-current` | No docstring, README or comment beside the changed code still describes the pre-alignment variant. |
| `tests-exercise-change` | The tests that pass actually exercise the changed path, rather than passing because they never reach it. |
| `no-behavior-change` | The aligned module behaves identically to before alignment: no changed outputs, side effects or error paths. |

Mapping from the judge's outcome to the module verdict:

| judge outcome | module verdict |
|---|---|
| `pass` | `PASS` |
| `fail` where `no-behavior-change` failed (its `pass` is false or its score is under the threshold) | `FAIL` |
| any other `fail` | `PASS-WITH-GAPS`, carrying the failing criteria's evidence |
| `abstain` (a judge that returned nothing or died included) | `PASS-WITH-GAPS`, carrying the abstain reason |

A judge that found a changed output, side effect or error path has found the one thing a
`PASS` must exclude, so it can overturn a `PASS` to `FAIL`. A gap in coverage or docs, or
a judge that could not decide, cannot: the module is still fundamentally correct and needs
follow-up. An abstain is never a `PASS`. A test that fails outright is still decided by
the first verifier running the tests.

This replaces an adversarial re-check that was shown the first verifier's reasoning, and
that kept `PASS` when it returned nothing.

## What is not measured

The single-judge shape comes from an evaluation harness over cases with clear answers; it
does not show that the two-judge arrangement it replaces was worse in this pipeline. The
collapse here is a decision, not a measurement. The sealed set that would settle it, for
each rubric, is: cards (or aligned modules) whose right verdict is known, including
planted wrong picks (or planted uncovered changes), measured for false passes and false
fails separately.
