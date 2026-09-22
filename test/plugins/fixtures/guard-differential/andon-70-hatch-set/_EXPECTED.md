# andon-70-hatch-set

Issue #70: before this fix, the only way to bypass a wrong or unwanted denial
was to edit `.claude/andon.local.md` to set `enforcement: off` -- the most
destructive escape hatch (it disables the guard for every future call in the
whole repo, not just the one blocked edit). At `base` there is no per-call
override at all, so `ANDON_DISABLE_GUARD=1` in the environment does nothing
and the old guard denies on the live stop condition (a gap with no
`blast_radius`).

The fix checks `os.environ.get("ANDON_DISABLE_GUARD") == "1"` first thing in
`main()`, before stdin is even read, and returns `allow()` unconditionally --
the narrowest of the three remedies now named in every deny reason (`retire`
the stale record, this one-call env var, or `enforcement: off` as the
last-resort wholesale option). `_ENV` sets exactly that variable for this
case, so the new guard allows the edit.
