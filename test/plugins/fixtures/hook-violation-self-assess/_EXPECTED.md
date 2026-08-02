# hook-violation fixture for self-assess

`guard_target_edit.py` is inert unless a self-assess remediator dispatch has
an edit-scope lock open (`analysis/self-assess/edit_scope.json`) -- a repo
merely having `.claude/self-assess.local.md` present with neither
`idiom_fix.mode: fix` nor `transform.mode: execute` set is NOT a violation
under the current contract; it must ALLOW (that used to be this fixture's
violating scenario, and denying it was the bug: every edit from every other
plugin, or a direct edit, got swept into this gate the moment a repo looked
self-assess-managed at all).

This fixture instead has an edit-scope lock open naming `src/api.py` under
`mode: "idiom_fix"`, as if `self-assess-idiom-fix` had dispatched
`idiom-remediator` for it -- but `.claude/self-assess.local.md` never
actually sets `idiom_fix.mode: fix` (it defaults to `"propose"`). This
proves the mode gate is still a real, defense-in-depth check even while a
scope is open, not just a path-membership check: `guard_target_edit.py`
must deny editing `src/api.py` via `check_idiom_fix_mode` (rule:
idiom-fix-mode-fix-gate), even though the file is exactly the one the open
scope names.

Requires `.git` at the fixture root before probing (dirty-tree-gate needs a
git repo, and runs before the mode check). verify-hooks-deny.py's
`_GIT_INIT` marker convention does this.

PASS = exit 2, reason cites idiom-fix-mode-fix-gate.
FAIL = exit 0 (the edit would silently proceed unauthorized).
