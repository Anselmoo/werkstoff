# Seeded defect: sub-cycle thrash must escalate, not backtrack a 4th time

Behavior contract §3, "Sub-cycle thrash escalation":

> Given the same wire reopens after being re-proven three times within one
> sub-cycle history, the loop MUST stop treating it as a bounded backtrack
> and instead treat it as the stream's current constraint, escalating
> rather than continuing to backtrack indefinitely.

This fixture seeds a ledger where the wire `producer -> consumer` has already
reopened **three** times. A correct implementation must escalate it to the
stream's constraint. It must NOT open a fourth backtrack.

PASS = output names this as the constraint / escalates / refuses a 4th attempt.
FAIL = a fourth backtrack is opened, or the reopen count is not consulted.
