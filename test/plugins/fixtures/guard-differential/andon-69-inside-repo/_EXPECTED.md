# andon-69-inside-repo

The anti-loosening half of the #69 pair. Same ledger, same live stop
condition (a gap with no `blast_radius`), but the edit target is
`src/api.py` -- a real source file inside the probe repository. The new
containment check added for #69 must not let a normal in-repo edit slip
through: `resolved` is inside `cwd` by both the lexical and the realpath
test, so the containment branch does not fire and `stop_reason()` still runs
and denies, exactly as it did before the fix. Both the old and the new guard
deny this write.
