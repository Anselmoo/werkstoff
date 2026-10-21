# befund judge rubrics

befund asks a model one question that no command can answer: does a P0 business rule
hold? This file names the rubric for it. The contract it follows is in
`judge-contract.md` beside this file (a vendored copy, never edited here).

## Why a judge, and not a command

Whether `file:line` contains the logic a rule claims, and whether that logic executes,
has no exit code to ask. A parser can say the line exists; it cannot say the line
implements "payroll accounts are fee-exempt". So the contract's first step -- a command
decides where one can -- finds nothing to decide here, and one judge is asked.

## `befund-p0-rule@1`

One judge call per P0 rule. The item is the rule's `id`, echoed back verbatim.
Threshold `0.7`: the verdict fails when any criterion has `pass: false` or the lowest
criterion score is below `0.7`.

| criterion id | question the judge answers |
|---|---|
| `citation-contains-logic` | Does the cited `file:line` contain the logic the rule claims? |
| `logic-executes` | Is that logic executing code, and not only a comment or docstring? |
| `rule-faithful` | Does the rule statement stay within what the code does, without over-generalising it? |

The same three ids, questions and threshold are the `P0_RUBRIC` constant in
`scripts/lib/p0_panel.py`, and `scripts/lib/test_p0_panel.py` fails if this table and
that constant disagree. Raise the `@1` on any change to a question or the threshold.

## What the judge returns

Only the report below. It does not state a pass, a fail or a score for the whole rule.

```json
{
  "item": "RULE-003",
  "criteria": [
    {"id": "citation-contains-logic", "score": 0.95, "pass": true, "evidence": "src/billing/overdraft.py:58 tests is_payroll before the fee is computed"},
    {"id": "logic-executes", "score": 0.9, "pass": true, "evidence": "line 58 is an if-branch in charge_overdraft_fee, called by the nightly batch"},
    {"id": "rule-faithful", "score": 0.85, "pass": true, "evidence": "the branch exempts payroll accounts only; the rule says the same"}
  ],
  "abstain": false,
  "abstainReason": null
}
```

A judge that can decide some criteria but not one of them gives that one `"score": null` and
`"pass": null`, with evidence naming what would decide it (verdict@2). A judge that cannot read
the citation at all says so with `"abstain": true` and a reason.

## What code decides

`befund_cli.py p0-confirm` hands the report to `judge_contract.decide`, which returns the
decided verdict: `outcome` is `pass`, `fail` or `abstain` (a failed criterion is a `fail` even
beside an undecidable one), `score` is the lowest decided criterion score, and `calibrated` is derived from a calibration record the rubric does not have.
The verdict is stored on the rule as `p0_verdict`. `validate-artifact --kind
business_rules_summary` accepts a P0 rule only when its `p0_verdict` is a well-formed
verdict, from `befund-p0-rule@1`, about that rule's own id, with outcome `pass`. A fail,
an abstain, a missing verdict or the old `panel_confirmed: true` is refused.

## Calibration status

**Uncalibrated.** No known-answer cases exist for this rubric and no sealed set has been
measured, so there is no `calibration` record and every verdict carries `calibrated:
false`. Each run shows the user a sample of verdicts (`p0-spot-check`) with that label.
Until a sealed set exists, a `pass` here means one judge read the citation and found
support, not that agreement with a human has been measured.

## What replaced the two-judge panel

Two judges with distinct ids, both voting yes, used to confirm a P0 rule. They are
collapsed into one contract judge as part of issue #119 (one LLM-as-judge contract for all plugins). The finding behind
that choice comes from an evaluation harness over test cases with clear answers; it does
not show that two judges inside this pipeline were worse. The old panel also had two
defects of its own (a `"no"` vote counted as yes, and a repeated `judge_id` overwrote the
first vote), which the decided verdict removes whichever way the single-versus-two
question comes out. Whether one judge confirms the same rules two did is unmeasured:
running the old panel and the new judge over the same P0 rules, and comparing which rules
each confirms, is the measurement that would settle it.
