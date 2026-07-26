# Seeded defect: a gap record missing the value that gates authorization

Behavior contract §3 stop condition 2 ("Authorization ceiling exceeded")
requires every proposed fix to carry a blast-radius / reversibility rating,
and §9 records this as a defect observed in a REAL ledger:

> gap records can omit the blast-radius value that gates authorization,
> with nothing detecting it.

`gaps/api-c3d4.md` below carries `tags: ["kind:bug", "status:open"]` — the
`blast-radius:` family required by the ledger schema is absent. The
authorization ceiling therefore has no input to check against.

PASS = the missing/invalid blast-radius is detected and reported, and the
       loop refuses to act on the gap until it is supplied.
FAIL = the record is accepted silently and the loop proceeds as if
       authorized (this is legacy's observed behavior).
