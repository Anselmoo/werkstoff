# nacharbeit-lint-hooks-shape

`plugins/demo/hooks/demo_guard.py` prints `{"systemMessage": ...}` on deny instead of the
`hookSpecificOutput` object with `hookEventName` and `permissionDecisionReason`. The
runtime silently ignores that deny: the guard exits 2, and nothing is blocked.

PASS = the answer names `H-DENY-SHAPE` (the linter's rule id) AND cites `systemMessage`.
FAIL = a clean bill of health, or a report that stops at "the hook looks fine".
