# Seeded defect: one record holding two independent gaps

Behavior contract §9 records this as observed in a REAL ledger:

> a single record can hold multiple independent gaps, which makes per-gap
> status and retry-counting ambiguous.

`gaps/docs-e5f6.md` below is titled "2 contradictions" and describes two
unrelated problems in one record with a single shared `status:open`.

Consequences a correct implementation must avoid:
  - fixing one contradiction leaves no representable state (the record is
    either wrongly closed or wrongly still open)
  - a per-gap retry/reopen count is ambiguous — attempts against one
    contradiction are indistinguishable from attempts against the other

PASS = the multi-gap record is detected and rejected or split, so each gap
       carries its own status and retry count.
FAIL = it is accepted as a single unit (this is legacy's observed behavior).
