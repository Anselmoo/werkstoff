# hallucinated-dependency fixture

Pins `quality-cycle`'s fix-mode case for `dependency_audit`:
`left-pad-definitely-not-real-9f3a` does not exist on the npm registry.
`quality-dependency-audit` should flag it High-severity; `quality-cycle` in
`fix` mode should have `quality-remediator` remove the line, then re-run
`quality-dependency-audit` to confirm the manifest is clean, and mark the
finding `fixed` in `ledger.json`.
