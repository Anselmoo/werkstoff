# hallucinated-dependency fixture

Pins `zeugnis-cycle`'s fix-mode case for `dependency_audit`:
`left-pad-definitely-not-real-9f3a` does not exist on the npm registry.
`zeugnis-dependency-audit` should flag it High-severity; `zeugnis-cycle` in
`fix` mode should have `zeugnis-remediator` remove the line, then re-run
`zeugnis-dependency-audit` to confirm the manifest is clean, and mark the
finding `fixed` in `ledger.json`.
