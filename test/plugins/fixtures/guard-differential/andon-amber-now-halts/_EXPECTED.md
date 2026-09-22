# andon — an unrecognised verdict must halt, not advance (old=allow, new=deny)

## The scenario

An open gap with a valid blast radius, and one evidence record for the wire reading
`verdict: amber`.

`amber` is not in `andon_core.WIRE_VERDICTS`, not in `okf-ledger-schema.md:83`, and no writer
emits it — but `tools/andon-ledger-validator/validate_ledger.py:51` accepted it as a valid
gating value, so a ledger containing one passed validation.

## Why this pair is the right pair

The old hook read:

    NON_ADVANCING_VERDICTS = ("red", "unknown")
    if verdict and verdict.lower() in NON_ADVANCING_VERDICTS:

A denylist of bad values. Every verdict outside it — including `amber`, and including any
typo, any value from a newer schema, any hand-edited string — **advanced**. The hook failed
open.

What makes this worse than a plain gap is what the rest of the system did with the same
record at the same moment: `compute_wire_status` (`andon_core.py:1016-1026`) collapses
anything non-green/non-red to `unknown`, and the board draws `unknown` as an amber edge
labelled *verdict hung — unproven*. So the operator saw an unproven wire on the board while
the PreToolUse hook let every edit through. Looks gated, isn't — the exact failure this
plugin exists to prevent, inside the plugin.

The fix inverts the test to an allowlist of good: a wire advances only on an explicit
`green`.

## Its partner

`andon-green-still-advances` is the other half: `verdict: green`, allow before and allow
after. Without it, inverting the polarity could have gated *everything* and this case alone
would still have passed. Note the polarity is the mirror of PR #95's pairs — those fixed
over-denial, so their unchanged half is a deny; this fixes under-denial, so its unchanged
half is an allow.
