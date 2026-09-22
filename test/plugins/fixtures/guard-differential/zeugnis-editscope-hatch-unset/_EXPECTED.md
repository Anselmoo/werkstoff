# zeugnis — the hatch is opt-in (old=deny, new=deny)

## The scenario

Identical to `zeugnis-editscope-hatch-set`, with no `_ENV` file.

## Why this pair is the right pair

The anti-over-reach half. An escape hatch added as statement #1 of `run()` sits in front of
every other check in the file, so getting its condition wrong disables the guard outright and
silently — and `verify-hooks-deny.py` would still pass, because it probes a violating edit
with a clean environment and would see exactly this case.

Testing truthiness instead of `== "1"`, or reading the wrong variable name and defaulting
open, both produce a hook that allows everything while looking correct. This case pins that
the default path is untouched.

`test_guard_edit_scope.py::TestEscapeHatch::test_other_values_do_not_bypass` covers the
neighbouring values (`"0"`, `"true"`, `"yes"`, `""`) that a truthiness test would wrongly
accept.
