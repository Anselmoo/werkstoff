# Rule Card worked examples

Illustrative examples from a hypothetical e-commerce codebase -- replace
their content entirely for whatever repo you are actually mining. These
exist to show `rule-card-template.md`'s schema filled in with concrete
values, not to be copied verbatim into a real report.

## A confirmed P1 rule (no judge required)

```
### RULE-014: Gold-tier checkout discount
**Priority:** P1
**Confidence:** High
**Citation:** `src/checkout/pricing.py:142`
**Specification:**
  Given a cart subtotal of $84.50 and a saved loyalty tier of "gold"
  When  checkout totals are computed
  Then  a 12% discount is applied before tax (subtotal x 0.88, rounded half-up to cents)
**Status:** confirmed
```

## A confirmed P0 rule (judge-verified)

```
### RULE-003: Overdraft fee waiver on payroll accounts
**Priority:** P0
**Confidence:** High
**Citation:** `src/billing/overdraft.py:58`
**Specification:**
  Given an account flagged is_payroll = true with a negative balance
  When  the nightly overdraft-fee batch runs
  Then  no overdraft fee is charged (payroll accounts are fee-exempt by statute)
**Status:** confirmed
  Judge verdict pass (befund-p0-rule@1, score 0.85, uncalibrated): the judge
  re-read src/billing/overdraft.py:58 and verified the is_payroll exemption.
```

## A P0 rule that did not pass the judge -- not a card at all

`RULE-007` (an interest-rate cap on promotional balances) was mined at
priority P0, but the judge could not read the cited file and abstained
(`abstainReason: "judge:src/rates/promo.py not found at the cited commit"`), so
its `p0_verdict.outcome` is `abstain`. Per `befund-extract-rules` Step 3, this
rule is downgraded to `unconfirmed` and listed separately in
`BUSINESS_RULES.md`'s "Unconfirmed rules" section (see
`business-rules-report-sample.md`) with that reason. It never gets a Rule Card,
and a `fail` is treated the same way: only `pass` confirms.
