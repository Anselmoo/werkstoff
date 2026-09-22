# befund #39 — the containment allow must not become a bypass (old=deny, new=deny)

This is the third case in #39's set, and the one that pins the *direction* of the
containment test rather than its presence.

## The scenario

An edit-scope lock is open naming only `src/api.py`. The write targets
`<parent>/outside/looks-outside.py`, which `_SETUP.py` creates as a symlink to
`src/secret.py` — in-repo source that the lock does **not** name.

Lexically the target is outside `cwd`. By realpath it is inside. The write lands on
unlisted repository source, so `remediator-scope-enforcement` is exactly what it is
about, and both revisions must deny.

## Why this pair is the right pair

`befund-39-outside-repo` proves the fix does something; `befund-39-inside-repo` proves
it did not delete the rule. Neither can fail if the containment test is written with
the two halves combined the wrong way round, because in both of them the lexical and
realpath answers agree.

This case is the one where they disagree, and it is the whole reason the check needs
two tests instead of one. The first implementation read:

    if not (_is_contained(lexical, cwd_norm) and _is_contained(real, cwd_real)):
        return allow()

which allows whenever *either* test says "outside" — so the disagreement resolved in
favour of allowing, and this write sailed past the scope lock. The guard before the fix
denied it. That is a bypass introduced by the fix, and only this case sees it.

The correct form allows only when both agree the target is outside, so either one
saying "inside" keeps it gated. `arbeitsplan_guard.py:430-432` states the invariant that
survives the inversion: realpath "only ever narrows what is allowed here, never widens
it."

## Note on construction

The symlink is built by `_SETUP.py` at run time, not committed. Two reasons, and the
second one bit first:

1. The fixture directory *becomes* the probe repo, so there is no "outside" to commit
   into. `{PARENT}` in `_EVENT.json` names the repo's parent at run time.
2. `probe_repo()` used to dereference committed symlinks — `shutil.copytree` defaults to
   `symlinks=False` and `shutil.copy2` to `follow_symlinks=True` — so a committed
   symlink arrived in the probe copy as an ordinary file and the case tested nothing.
   The runner now preserves them, and `_SETUP.py` asserts `is_symlink()` and the resolved
   target anyway rather than trusting it.
