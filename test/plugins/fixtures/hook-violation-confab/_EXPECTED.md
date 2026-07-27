# hook-violation fixture for confab

An active remediation-scope lock (`analysis/confab/remediation_scope.json`)
authorizes editing exactly `src/correct_file.py` for finding `F1`. Editing
`src/api.py` instead — outside the locked scope — must be denied by
`hooks/guard_edit_scope.py` (rule: remediator-one-fix-per-finding).

No `_GIT_INIT` needed — confab's hooks do not check git cleanliness.

PASS = exit 2, reason cites remediator-one-fix-per-finding / allowedFile.
FAIL = exit 0 (the out-of-scope edit would silently proceed).
