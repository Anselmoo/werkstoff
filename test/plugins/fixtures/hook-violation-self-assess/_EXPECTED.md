# hook-violation fixture for self-assess

Self-assess-managed (`.claude/self-assess.local.md` present) but neither
`idiom_fix.mode: fix` nor `transform.mode: execute` is set (both default to
their non-authorizing value). Editing `src/api.py` — target-repo source,
outside `analysis/self-assess/` — must be denied by
`hooks/guard_target_edit.py` (rules: idiom-fix-mode-fix-gate,
transform-execute-gate-transform-mode).

Requires `.git` at the fixture root before probing (dirty-tree-gate needs a
git repo). verify-hooks-deny.py's `_GIT_INIT` marker convention does this.

PASS = exit 2, reason cites idiom-fix-mode-fix-gate or the transform gate.
FAIL = exit 0 (the edit would silently proceed unauthorized).
