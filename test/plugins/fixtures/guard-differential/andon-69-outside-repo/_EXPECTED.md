# andon-69-outside-repo

Issue #69: the hook resolves the edit target only to check whether it IS the
ledger (`resolved == ledger or ledger in resolved.parents`), then falls
straight through to `stop_reason()` and denies on the ledger's own stop
condition regardless of where the target actually is. A gap with no
`blast_radius` value is a live stop condition here (`analysis/andon/ledger/
gaps/g0.md`), so at `base` the old guard denies a write to
`/Users/example/.claude/plans/notes.md` -- a file that has nothing to do with
this repository or its ledger, and is not even inside it.

(A literal `$HOME` cannot be baked into a committed fixture -- it differs per
machine and per CI runner -- so this uses a fixed, portable stand-in absolute
path that is guaranteed to fall outside any temp probe directory the
differential runner creates. What matters for the defect is only that the
target is a real absolute path outside the probe repository; the hook's
`Path.resolve()` does not require the file to exist.)

The fix adds a containment check before `stop_reason()` runs at all: if the
resolved target is not inside `cwd` (by both a lexical `normpath` test and a
`realpath` test agreeing), the hook returns `allow()` immediately -- the andon
rule has nothing to say about a file outside the repository it's declared
over. The new guard therefore allows this write.
