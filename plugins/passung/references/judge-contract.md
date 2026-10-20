# Judge verdict contract (verdict@1)

This file is vendored byte for byte. Do not edit a copy: change the canonical copy and
vendor it again. A sync check fails on any difference.

Any step in this plugin that asks a model whether something holds follows this contract.
The model reports evidence. Code turns the report into a pass or a fail.

## Contents

1. A command decides first
2. One judge call per item
3. Code decides the outcome
4. Calibrated, or labelled uncalibrated
5. A human sees a sample every run
6. What this contract does not claim

## 1. A command decides first

If an exit code, a parser, a test, a schema or a probe can answer the question, it answers
it, and no model is asked. The command's result is recorded as a verdict with
`decidedBy: "command"`: each criterion it checked scores `1.0` with `pass: true`, or `0.0`
with `pass: false`, and the evidence is the command and its output. A model is asked only
for what no command can decide.

## 2. One judge call per item

Each item is judged in a single call, against a named rubric:

```json
{
  "id": "<plugin>-<name>@<int>",
  "threshold": 0.7,
  "criteria": [
    { "id": "grounded", "question": "Does the cited location contain the claimed logic?" },
    { "id": "relevant", "question": "Does the claim bear on the item asked about?" }
  ]
}
```

The rubric's id and criteria are listed in this plugin's references. Raise the `@<int>` on
any change to a question or the threshold, because a verdict is only comparable to verdicts
from the same rubric version.

The judge returns only this, under a strict schema:

```json
{
  "item": "the id it was asked about, verbatim",
  "criteria": [
    { "id": "grounded", "score": 0.9, "pass": true, "evidence": "src/a.py:20-35 computes it" },
    { "id": "relevant", "score": 0.8, "pass": true, "evidence": "the item names src/a.py" }
  ],
  "abstain": false,
  "abstainReason": null
}
```

A judge that cannot judge says so with `"abstain": true` and a reason. Abstaining is an
honest answer. A guessed score is not.

## 3. Code decides the outcome

The judge never states the outcome. `decide()` in Python, or `decideVerdict()` in a
workflow, computes it the same way every time:

| outcome | when |
|---|---|
| `abstain` | the report is missing or not an object; it names no item or a different item; `abstain` is not a boolean, or is true; any rubric criterion is missing, duplicated or unknown; any score is not a number in [0, 1] (a boolean is not a number); any `pass` is not a boolean; any evidence is empty |
| `fail` | the report is well-formed, and any criterion has `pass: false`, or the **minimum** criterion score is below the threshold |
| `pass` | everything else |

- **`score` is the minimum, never an average.** If three criteria pass and a fourth fails,
  the verdict fails.
- **An abstain is never a pass.** Anything that gates on the verdict treats an abstain as
  not passed, and reports it separately from a fail.
- **`abstainReason` is a fixed code** such as `missing-criterion:<id>` when code abstained,
  or `judge:<text>` when the judge abstained. Every abstain can be traced to a cause.

The decided verdict has these fields: `item`, `rubric`, `decidedBy`, `criteria`,
`abstain`, `abstainReason`, `threshold`, `score`, `outcome`, `calibrated`.

## 4. Calibrated, or labelled uncalibrated

A judge is trusted only after it has cleared a floor on known answers it was never tuned
on:

- **A tuning set** of cases whose right verdict is known. The judge prompt may be revised
  against it.
- **A sealed set** that is never shown during tuning. It is measured once, after the
  prompt is frozen.
- **Agreement**, reported with every run: the fraction of sealed cases where the judge's
  outcome matched the known outcome. Report false passes and false fails separately. A
  judge can reach high agreement by passing everything when most cases are passes.

The rubric records that measurement as `calibration: {sealed, agreement, floor}`.
`calibrated` is true only when `sealed > 0` and `agreement >= floor`. It is derived from
that record and never declared. A rubric with no record is uncalibrated, and every verdict
it produces says so.

## 5. A human sees a sample every run

Each run returns `spotCheck`, a deterministic sample of its verdicts, and the step that
ran it shows that sample to the user, including evidence and outcome:

- sorted by item id, then taken in a stride from first to last (three verdicts gives the
  first, the middle and the last)
- never random, so the same run always shows the same sample

An uncalibrated judge's verdicts are shown with that label.

## What this contract does not claim

One judge call per item, scored from 0.0 to 1.0 with a pass or fail, has been reported
as the most consistent with human judgement, but that finding comes from an evaluation
harness over test cases that had clear answers. It does not show that a multi-agent
tribunal inside a pipeline is worse. Where a plugin keeps such a tribunal, the reason
is recorded as unmeasured, together with the paired measurement that would settle it.
