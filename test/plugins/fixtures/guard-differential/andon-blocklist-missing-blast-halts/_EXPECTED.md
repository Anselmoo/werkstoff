# andon — a block list missing a required field still halts (old=deny, new=deny)

## The scenario

Identical to `andon-blocklist-read-allows` with the `- blast-radius:...` item removed.

## Why this pair is the right pair

The anti-over-reach half, and it guards the more dangerous direction. Teaching the parser to
read block lists moves a class of record from "unreadable, therefore halted" to "readable".
The tempting mistake is to treat *parsed* as *satisfied* — to stop halting on block-list
records generally, rather than on the specific values they now yield.

Here the record parses cleanly and the blast radius is genuinely absent. Contract §9.2 is
unambiguous that this halts and that the value is never inferred, so the answer must not move.

Both revisions deny, for different reasons: before the fix because `tags` was empty and
nothing could be read; after, because the list was read and the field is not in it. Same
verdict, different cause — which is why the `_EXPECTED.md` matters as much as the pair.
