# befund-39-inside-repo

The anti-loosening half of the issue #39 pair: the same edit-scope lock as
`befund-39-outside-repo` is open (naming only `src/api.py`), but this time the Edit targets
`src/other.py` -- a relative, IN-REPO path that resolves inside the probe repository, and is
simply not one of the files the open lock named.

## old=deny and new=deny (the rule the fix must not loosen)

This is exactly the case `remediator-scope-enforcement` exists for: a remediator dispatch is
authorized to touch only the files its edit-scope lock names, and `src/other.py` is not one of
them. Both the pre-#39-fix guard (base `b029676`) and the fixed guard deny this edit with the
same `remediator-scope-enforcement` message.

The new containment check added for issue #39 does not change this outcome: `src/other.py`
resolves (lexically and via realpath) to a path inside the probe repository, so containment
passes and control reaches the same `own_output_dir` / `allowedFiles` logic the old guard ran --
which still denies, because the target is genuinely in-repo and genuinely not in the lock's
`allowedFiles`. Pairing this with `befund-39-outside-repo` (deny -> allow) is what proves the
fix narrows the defect rather than loosening `remediator-scope-enforcement` itself: an in-repo
file outside the lock is refused exactly as before.
