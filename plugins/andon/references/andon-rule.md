# The andon rule: three non-negotiable stop conditions

Named after the manufacturing andon cord: any station on the line can halt
the whole line rather than pass a defect downstream. `andon-loop` enforces
three specific halts, all implemented in `scripts/andon_core.py
check_stop_conditions()` -- this document explains each; the function is
what actually blocks advance.

## Condition 1: red verdict blocks advance

If `andon-verify` returns `red` for a wire, `andon-loop` must not advance
past it. The only ways past a red wire:

- An explicit user re-run of `andon-verify` that produces new evidence
  (a fresh attempt, not the same evidence re-argued).
- An explicit user override or defer of the gap (the user consciously
  chooses to accept the risk or postpone the gap, not the loop deciding
  this on its own).

`check_stop_conditions(verdict="red", ...)` blocks unless
`user_confirmed_red_override=True` was explicitly passed -- which only
happens when the user actually said so, never as a default.

## Condition 2: blast-radius exceeding authorization halts advance

A proposal's blast-radius tag is compared against the configured
`authorization_level` on the ordering `local+reversible < hard-to-reverse <
shared-state-visible`. If the proposal exceeds the ceiling, `andon-loop`
halts **before applying the fix** and asks the user to either explicitly
raise authorization or explicitly skip the gap. This is not a warning that
gets logged and continued past -- it is a real halt until one of those two
explicit choices is made.

## Condition 3: Tier 1 structural contradiction is non-overridable

If `andon-verify` strategy e (structural graph, see
`skills/andon-verify/references/structural-graph-tiers.md`) returns a Tier 1
contradiction -- a real Kythe/SCIP/LSIF index query directly refutes a
claimed structural edge -- `andon-loop` halts and **nothing can override
it**: not the `andon-adjudicator` agent, not a human confirmation flag, not
a re-run with different arguments. This is enforced by construction in
`check_stop_conditions()`: there is no parameter in that function's
signature that can satisfy this branch. The only way past it is for a
*different, non-contradicting* Tier 1 (or lower-tier) proof to supersede the
original claim -- i.e. the claim itself needs to change, not the gate.

## Supersession and expiry (#72)

An evidence doc's `superseded_by` field names the slug of a *different*
evidence doc that replaces it -- this is the mechanism condition 3's closing
line above actually points at ("the claim itself needs to change, not the
gate"): a fresh, non-contradicting proof supersedes the old claim by being
recorded as its successor, not by editing the original doc in place (the
ledger is append-only). `superseded_by` can chain across several records;
both `andon_core.compute_wire_status()` and the PreToolUse hook's
`stop_reason()` resolve the chain transitively to its **head** -- the record
nobody supersedes -- and judge *that* record's verdict, never an
intermediate or leaf record's. A `superseded_by` naming a slug that does not
exist, or a chain that cycles back on itself, denies outright wherever in
the chain it occurs -- fail closed, never a silent fall-back to the
unresolved record's own verdict.

`valid_until` (an ISO `YYYY-MM-DD` date) puts a shelf life on an evidence
doc: once that date has passed, the record gates as verdict `unknown` no
matter what it actually recorded, on the theory that a green verdict from
before some known drift point is no longer trustworthy on its own. Expiry is
judged on the chain **head** only -- an expired `valid_until` on a
superseded, non-head record has no effect, and a non-expiring head is
unaffected by an expired leaf pointing at it.

`measured_against` carries no gating behavior of its own; it is a free-text
pointer (typically to the decision record a strategy was checked against)
that gets named verbatim in any deny reason the evidence doc causes, so a
human reading the halt knows what standard was applied.

## Why condition 3 has no override, and conditions 1-2 do

Conditions 1 and 2 are judgment calls about risk the loop cannot make for
the user -- a red verdict might be a false negative, a big blast radius
might be exactly what the user wants today. A human is the right party to
decide. Condition 3 is different in kind: a real structural index is ground
truth about what the code actually does, not a judgment call. Overriding it
would mean asserting the code does something the index proves it doesn't --
there is no legitimate reason to do that, so no override path exists.
