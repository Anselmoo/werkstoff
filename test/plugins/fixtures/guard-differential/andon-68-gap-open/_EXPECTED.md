# andon-68-gap-open

The anti-loosening half of the #68 pair. Identical evidence doc
(`analysis/andon/ledger/evidence/wire-a-b.md`, `verdict: unknown`,
`wire: stage-a->stage-b`), but this time the gap that names it in
`resolved_by` is missing entirely -- `analysis/andon/ledger/gaps/g0.md`
records the same wire as still `status: open` (with a `blast_radius` set so
the ONLY live stop condition is the evidence verdict, not the separate
missing-blast-radius check). Nothing in this ledger says the gap the
evidence would resolve is closed, so the #68a skip-list stays empty and the
`unknown` verdict must still gate. Both the old and the new guard deny this
write -- the fix only stops gating evidence whose gap was actually closed,
never evidence in general.
