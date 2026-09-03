# lehre-fidelity-gap

Every rule in the ruleset PASSES on `src/adapters/*`. No layering violation, no
bare except, no forbidden import. The seeded defects are not rule violations at
all — they are the unit failing to be what it was for, which is the one thing no
rule in the doctrine can express.

## Gap 1 (designed) — vendor_c is absent

The recorded `intent` names three vendors; only `vendor_a` and `vendor_b` exist.
`get_adapter` does `REGISTRY.get(name)`, returning `None` for an unknown vendor
rather than raising, so the omission is **silent** at runtime.

## Gap 2 (unintended, kept deliberately) — nothing is normalised

Found by a real run during the N=5 determinism sweep, not by the fixture's
author. `contracts/schema.py` declares `RowSchema.fields = ("vendor", "sku",
"qty", "price")`, but `vendor_a.rows()` returns raw `csv.DictReader` dicts keyed
by the source file's own headers and `vendor_b.rows()` returns raw positional
lists. Neither maps onto `RowSchema`, so the intent's core promise —
"normalises them to one schema" — is not implemented.

This was seeded by accident and is being KEPT, not removed. Removing it would be
tuning the fixture to match what the oracle happens to look for, which is the
same error as retuning an oracle to match a result. It also makes the case
better: two independent gaps mean a thorough run is distinguishable from a
shallow one, even though the oracle only requires the first.

## Correct behaviour

`lehre-validate` reports the fidelity gap(s) and **refuses to close** the
`adapters` unit. Closing it on a clean rule sweep is the failure this fixture
exists to catch. `contracts` is already closed so the ordering gate does not
mask the check.
