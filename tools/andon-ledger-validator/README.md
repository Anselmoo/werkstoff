# andon-ledger-validator

A stdlib-only validator for andon's persisted ledger records. It exists
because of what a **real** ledger looked like, not because of an argument
about what ledgers ought to look like.

## The evidence

Measured against `spectrafit-core`'s andon ledger (commit `55e2c4f^`,
66 gap records + 35 evidence records):

| Gating field | in frontmatter | in body prose | absent |
|---|---|---|---|
| `blast radius` (authorization ceiling input) | **0/66** | 65/66 | 1/66 |
| `on constraint` | **0/66** | 66/66 | 0 |
| `verdict` (the andon rule's input) | **0/35** | 35/35 | 0 |
| `non-overridable` | **0/35** | 35/35 | 0 |

Plus: `resource:` unused in 66/66 gap records (correctly used in 35/35
evidence records), and **22/66 descriptions + 12/66 titles severed mid-word**
by a length cap — e.g. a claim ending `...Additionally, SolverMeta is NOT amo`.

The headline is not "a field was missing." Exactly one record was missing one.
The headline is that **every field gating a downstream decision lives only as
free text in a markdown bullet, in 100% of records.** That is a worse failure
mode than absence: an absent field announces itself the moment something looks
for it, whereas prose looks present to a human reviewer and is invisible to
every code path. Nothing in the system ever noticed.

## Two deliberate non-goals

**It is not a format change.** The ledger stays human-readable markdown with
frontmatter. JSON would have prevented none of the defects above — same
overloaded string, same prose bullet, same truncation, just in braces. The
missing thing is validation, which is orthogonal to serialization.

**It is not a repair tool.** It never fills in, infers, or normalizes a missing
gating value. Inferring an absent blast-radius rating is precisely the silent
data repair this exists to catch: the halt it produces is contingent on the
value the inferring code invented, and the invented value then persists into
the ledger for the next run to inherit as if a human had supplied it. A guard
whose outcome depends on a value it fabricated is not a guard. It reports; a
human fixes. `test_validator_never_supplies_a_value` pins this down.

## Severities and the two modes

| Severity | Meaning |
|---|---|
| `block` | The record is undecidable — the gating value exists nowhere, or is not in the declared enum. Nothing may proceed on it. |
| `migrate` | The value exists but only as body prose. Recoverable by a human moving it; never by this tool guessing the prose meant what it says. |
| `warn` | Shape problems that lose information but do not gate a decision — truncation, unused `resource:`. |

`--mode write` fails on `block` **or** `migrate`: newly written records must be
well-formed, or the defect keeps reproducing. `--mode read` fails only on
`block`, so a legacy ledger stays loudly reportable rather than unusable —
without that split, the 201 `migrate` findings above would make andon unable to
read its own production ledger at all.

## Usage

```bash
python3 tools/andon-ledger-validator/validate_ledger.py <ledger-dir> --mode read
```

```bash
python3 tools/andon-ledger-validator/test_validate_ledger.py
```

## Status: not yet wired in

`andon-loop` does **not** call this yet, deliberately. The A/B/C rebuild pilot
requires Arm A (`plugins/andon/`) to stay untouched as the baseline, and
editing `andon-loop/SKILL.md` to invoke the validator would change the very
behavior the pilot is measuring. Wiring it into the ledger read/write path is
the first follow-up once the pilot closes.
