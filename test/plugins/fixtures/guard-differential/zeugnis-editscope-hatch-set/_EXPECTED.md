# zeugnis — guard_edit_scope gains an escape hatch (old=deny, new=allow)

## The scenario

An open remediation-scope lock authorising exactly `src/correct_file.py` for finding `F1`.
The edit targets `src/api.py`, which the lock does not name — correctly denied — but
`_ENV` sets `ZEUGNIS_DISABLE_GUARD=1`.

## Why this pair is the right pair

This hook had **no** env escape hatch, failing `H-ESCAPE-HATCH`
(`plugins/nacharbeit/references/rubric.md:197`). Its only remedy was the one its own deny
message named: delete `analysis/zeugnis/remediation_scope.json`, or the whole
`analysis/zeugnis/` directory. That is destroying audit state in order to make one unrelated
edit — the same disproportionate remedy #73 complained about for the sibling Bash guard,
which got its `ZEUGNIS_DISABLE_GUARD` in PR #95 while this one was left behind.

The var is checked as statement #1 of `run()`, before stdin is read and before the filesystem
is touched, so a stuck denial always has an escape that costs nothing. Exact `== "1"`, not
truthiness, matching `guard_bash_scope.py:250`.

## Its partner, and one thing neither case covers

`zeugnis-editscope-hatch-unset` is the identical repo and event with no `_ENV`. Deny before,
deny after — the hatch is opt-in, not the new default.

Neither differential case can see the behaviour that actually distinguishes this hatch from
the Bash guard's: this hook is the **only writer of `consumed: true`** in the repo, and an
early return skips `mark_consumed`, so a bypassed edit does not spend the finding's one-shot
budget. That is deliberate — an edit the guard never judged should not count against a single
authorized fix — but it is stateful in a way `guard_bash_scope` is not. It is asserted in
`test_guard_edit_scope.py::TestEscapeHatch::test_bypass_does_not_spend_the_one_shot_budget`,
because a differential case only compares a decision, never a side effect.
