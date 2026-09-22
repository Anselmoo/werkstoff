# andon-68-gap-closed

Issue #68: `stop_reason()` scans every evidence file in filename order and
denies on the first `red`/`unknown` verdict, never checking whether the gap
that evidence resolved is already closed. Here `analysis/andon/ledger/
evidence/wire-a-b.md` records `verdict: unknown` for wire `stage-a->stage-b`,
and `analysis/andon/ledger/gaps/g0.md` is a `status: closed` gap whose
`resolved_by: "[[evidence/wire-a-b]]"` names that exact evidence doc as the
one that closed it -- i.e. a human has already re-verified this wire and
closed the gap, but the stale `unknown` evidence doc is still sitting in
`evidence/`.

At `base` the old guard has no way to join "this evidence resolved a gap"
back to "that gap is now closed" -- an evidence doc carries no gap
back-link, only the gap carries `resolved_by` pointing at the evidence -- so
it denies on the stale `unknown` verdict regardless.

The fix walks the gaps loop (which already visits every gap) and collects
the `resolved_by` slug of every CLOSED gap, then skips any evidence doc whose
filename stem is in that set. `wire-a-b.md`'s stem `wire-a-b` matches the
gap's `resolved_by` target exactly, so the new guard no longer gates on it
and allows the edit.
