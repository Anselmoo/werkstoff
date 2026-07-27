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

## Why condition 3 has no override, and conditions 1-2 do

Conditions 1 and 2 are judgment calls about risk the loop cannot make for
the user -- a red verdict might be a false negative, a big blast radius
might be exactly what the user wants today. A human is the right party to
decide. Condition 3 is different in kind: a real structural index is ground
truth about what the code actually does, not a judgment call. Overriding it
would mean asserting the code does something the index proves it doesn't --
there is no legitimate reason to do that, so no override path exists.
