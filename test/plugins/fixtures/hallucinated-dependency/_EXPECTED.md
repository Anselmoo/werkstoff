# hallucinated-dependency fixture

Pins `confab-cycle`'s fix-mode case for `dependency_audit`:
`left-pad-definitely-not-real-9f3a` does not exist on the npm registry.
`confab-dependency-audit` should flag it High-severity; `confab-cycle` in
`fix` mode should have `confab-remediator` remove the line, then re-run
`confab-dependency-audit` to confirm the manifest is clean, and mark the
finding `fixed` in `ledger.json`.
