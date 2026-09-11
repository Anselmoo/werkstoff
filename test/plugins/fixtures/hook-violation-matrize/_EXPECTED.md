# hook-violation fixture for matrize

`.design/` is present, so this is a matrize-managed repository and the guard is live.
`.design/references/apple-hig/type.css` is a collected reference: read-only by
invariant I1, which is how the copyright boundary is carried mechanically rather than
by good intentions.

The probe target is `.design/references/apple-hig/type.css` (via `_TARGET`) — an edit
into the reference store. The DEFAULT probe target (`src/api.py`) is deliberately NOT a
violation here and must be allowed: matrize's guard denies only inside the design root,
so a hook that denied the generic target would be policing the whole repository.

PASS = exit 2, reason cites the reference store being read-only.
FAIL = exit 0 (a reference would be edited in place, turning an extraction into a
derivative work).

The inert probe runs in an empty directory with no `.design/`, where the guard must
allow and say nothing at all.

## The second rule is not covered here

The guard's other refusal — denying a write to `system/tokens.json` or `out/` while a
`spread` choice record is unanswered — needs a second fixture state that would
contradict this one, so it is covered by `plugins/matrize/hooks/test_matrize_guard.py`
instead, which asserts both the deny and the allow for each rule.
