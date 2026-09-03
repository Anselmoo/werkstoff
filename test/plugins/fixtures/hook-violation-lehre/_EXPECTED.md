# hook-violation-lehre

A repository that has opted into lehre (`.lehre/ruleset.json` present) and declared a
build order: unit `api` depends on unit `contracts`, and `contracts` has **not** been
validated — `.lehre/units/contracts.done` is absent.

The default probe writes `src/api.py`, which unit `api` owns. lehre's guard must deny
it: the unit's dependency is unvalidated, so this write runs ahead of its beat.

This scenario is chosen deliberately over a content-based rule. The generic probe sends
an `Edit` event carrying `content` rather than `old_string`/`new_string`, so a
content-dependent rule would be decided through the guard's fail-closed reconstruction
path rather than through the rule itself — a deny for the right exit code and the wrong
reason. Unit ordering needs no file content, so this fixture tests the gate it names.

`src/contracts/` is deliberately absent too: nothing here should make the `contracts`
unit look complete.
