# BUSINESS_RULES.md -- a full rendered sample

What the actual `BUSINESS_RULES.md` output file looks like end to end,
including the branches that are easy to leave unspecified: a mixed run with
an unconfirmed P0, and the boring case where nothing was found at all.

## Sample: 2 confirmed rules, 1 unconfirmed P0

```markdown
# Business rules -- <repo name>

Mined <date>. 3 rounds run (converged: 2 consecutive dry rounds).

## Confirmed rules (2)

### RULE-014: Gold-tier checkout discount
**Priority:** P1
**Confidence:** High
**Citation:** `src/checkout/pricing.py:142`
**Specification:**
  Given a cart subtotal of $84.50 and a saved loyalty tier of "gold"
  When  checkout totals are computed
  Then  a 12% discount is applied before tax (subtotal x 0.88, rounded half-up to cents)
**Status:** confirmed

### RULE-003: Overdraft fee waiver on payroll accounts
**Priority:** P0
**Confidence:** High
**Citation:** `src/billing/overdraft.py:58`
**Specification:**
  Given an account flagged is_payroll = true with a negative balance
  When  the nightly overdraft-fee batch runs
  Then  no overdraft fee is charged (payroll accounts are fee-exempt by statute)
**Status:** confirmed
  Two-judge panel confirmed: judge-a and judge-b both independently
  re-read src/billing/overdraft.py:58 and verified the is_payroll exemption.

## Unconfirmed rules (1)

- **RULE-007** (interest-rate cap on promotional balances, P0): only one
  judge (`judge-a`) was independently dispatched before the round closed --
  `panel_confirmed` never reached `true`. Not included above; re-run the
  panel step to confirm or drop it.
```

## Sample: nothing found

```markdown
# Business rules -- <repo name>

Mined <date>. 2 rounds run (converged: 2 consecutive dry rounds).

No executable business/domain logic was found to mine in the scanned
lenses (calculations / validations-and-eligibility / state-and-lifecycle).
```

The empty-run branch is not an error -- a codebase can genuinely have no
mineable domain logic (e.g. a pure infrastructure/tooling repo). Report it
as a clean, explicit "found nothing," the same way `max_rounds_reached`
and `converged` are both legitimate stop reasons per Step 1 -- never as a
missing file or a silent skip.
