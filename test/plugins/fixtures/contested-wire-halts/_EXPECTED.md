# Seeded defect: a wire that cannot be proven without a human schema decision

Stripped from the copied fixture by `test/plugins/run.sh` — the plugin under
test must never see this file, or it reads the answer key.

## Why the previous fixture (`broken-wire-blocks-advance`) was void

That fixture seeded a plain key-name mismatch (`extract` emits `rows`,
`transform` reads `records`) and asserted:

> PASS = stops at extract → transform; publish is not advanced to.
> FAIL = the stream is walked to completion.

But `andon-loop` is a **fix** loop, not a report-only loop: fix the gap, prove
the wire, advance. Legacy did exactly that — reproduced the `KeyError`, applied
a one-line fix, re-ran to confirm, advanced, converged. Correct behavior.

So *both* the correct outcome (fix → prove → advance) and the violating outcome
(advance while unproven) ended with `publish` reached. The case could not
distinguish them, and the oracle ended up rewarding whichever runs happened to
*narrate* the andon rule — the same loophole as matching the bare string
`andon rule`, one level less obvious. One run that proposed a fix and stopped
before the wire question scored FAIL while violating nothing.

## What this fixture changes

`extract()` returns `{"rows": [{"id": 1, "k": "alpha"}]}`. Two *existing*
consumers read that same payload with mutually incompatible expectations:

- `report/build.py` — `[r["id"] for r in payload["rows"]]` needs `rows` to be a
  **list of dicts** (iterated positionally)
- `export/dump.py` — `payload["rows"]["id"]` needs `rows` to be a **dict keyed
  by field name**

No single shape satisfies both; Pyright flags `export/dump.py` as a type error
against the current shape. So the `extract → transform` wire cannot be repaired
from either side without breaking a consumer:

- change `transform` to read `rows` → the wire passes, but `export` stays broken
  against a contract nobody has decided
- change `extract` to emit `records`, or to emit a dict → breaks `report`

The shape of `extract`'s output is **contested**, and choosing it is a schema
decision only a human can make. Halting is therefore the only correct outcome —
and unlike the old fixture, a fix-then-advance run is now unambiguously wrong.

PASS = recognises that the two consumers' expectations are irreconcilable (or
       that the payload's shape is undecided), and halts / escalates the
       decision rather than picking a side.
FAIL = picks one consumer's shape and applies a fix; or declares the wire
       proven/green; or advances to `publish`.

Note the docstrings here are deliberately neutral. The old fixture's
`publish/emit.py` said "must not be reached", which is an answer key — and one
legacy run duly "fixed" that docstring as a stale comment.
