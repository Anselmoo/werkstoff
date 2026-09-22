# andon — a reopening wire below the threshold still advances (old=allow, new=allow)

## The scenario

Identical to `andon-reopen-count-halts` except that `log.md` stops at
`reopened (count 2)`, one below `MAX_CONSECUTIVE_REOPENS`.

## Why this pair is the right pair

This is the anti-over-reach half. Making the escalation stop reachable means teaching the
hook to read `log.md`, and the obvious way to get that wrong is to halt on the *presence* of
a sub-cycle line rather than on the count reaching the threshold.

That would be a serious regression: reopening a wire once or twice is the sub-cycle mechanism
working as designed. Only the third is the signal that the wire is the stream's constraint.
This case pins the boundary; `andon-reopen-count-halts` pins the other side of it.
