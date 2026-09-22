# andon-70-hatch-unset

The anti-loosening half of the #70 pair. Identical ledger and identical live
stop condition (a gap with no `blast_radius`), but no `_ENV` file, so
`ANDON_DISABLE_GUARD` is unset in the environment both runs. The new guard's
escape-hatch check (`os.environ.get("ANDON_DISABLE_GUARD") == "1"`) must not
fire on absence -- an unset or differently-valued variable is not "set to
bypass". Both the old and the new guard deny this write; the fix adds a way
to opt out on purpose, not a default bypass.
