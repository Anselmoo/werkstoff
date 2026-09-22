# andon — the sub-cycle escalation stop, reachable at last (old=allow, new=deny)

## The scenario

An open gap with a valid blast radius, and a `log.md` whose last sub-cycle line records
`ingest->normalize reopened (count 3)` — at `MAX_CONSECUTIVE_REOPENS`.

Contract §3's escalation condition says a wire that keeps reopening is the stream's
constraint, not a sub-cycle, and the loop must escalate rather than retry.

## Why this pair is the right pair

The old hook implemented that condition like this, inside the per-gap loop:

    reopens = tag_value(fm, "reopen_count") or tag_value(fm, "reopen-count")

**Nothing has ever written `reopen_count` onto a gap doc.** `build_tags_for_doc`
(`andon_core.py:423-441`) does not emit the tag; `track_subcycle` writes the count as a
`log.md` line and `parse_log_counters` re-derives it. The concept is keyed by **wire**, and a
gap has a `stage`, not a wire — so there is not even a per-gap value to write.

The branch was therefore unreachable on every real ledger. It was green only because
`test_andon_enforce.py`'s `GAP_THRASH` fixture hand-writes an inline `"reopen-count:3"` tag
that no production writer produces. A guard that passes its test and does nothing in the
field — which is the failure mode this plugin exists to detect.

The fix reads the count from where it actually lives.

## Its partner

`andon-reopen-under-threshold` is the identical ledger with the last line removed, so the
highest count is 2. Allow before, allow after. Without it, this case alone cannot tell
"escalation now fires at the threshold" from "any log with a sub-cycle line halts" — and the
second would stop the loop the first time a wire ever reopened, which is the normal case the
sub-cycle mechanism exists to permit.

## Note on the copied regex

The hook is stdlib-only and imports nothing from the plugin, deliberately: a hook that fails
to import denies every call. So it cannot call `parse_log_counters` and copies its
`sub_cycles` regex instead. `TestReopenParserAgreement` runs both parsers over the same log
text and requires the same answer, so the copy cannot drift silently.
