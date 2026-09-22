# andon — a green wire must still advance (old=allow, new=allow)

## The scenario

Identical to `andon-amber-now-halts` in every respect except the evidence verdict, which is
`green`.

## Why this pair is the right pair

This is the anti-over-reach half. `andon-amber-now-halts` proves the fail-open is closed; on
its own it cannot distinguish "unrecognised verdicts now halt" from "everything now halts",
and the second would be a far worse regression than the bug — a hook that denies every edit
in every andon repo.

Inverting `NON_ADVANCING_VERDICTS = ("red", "unknown")` into `ADVANCING_VERDICTS = ("green",)`
changes the answer for every value *except* `green` and the two already listed. So `green` is
precisely the input that must not move, and it is the only one.

## Note on polarity

PR #95's cases were `old=deny → new=allow`, because those defects were over-denial; their
unchanged half was `deny/deny`. This fix runs the other way, so the unchanged half is
`allow/allow`.

The runner originally **refused** an `allow/allow` pair, on the assumption that a guard fix
always loosens. That assumption was inherited from #95 and is wrong in general; it was
relaxed when this case was written, with the reasoning recorded at `load_case`. What makes a
pair a pair is that one case changes and one does not — which way round is a property of the
defect, not of the harness.
