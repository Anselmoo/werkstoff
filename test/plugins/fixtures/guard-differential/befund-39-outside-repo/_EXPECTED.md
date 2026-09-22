# befund-39-outside-repo

Reproduces issue #39: a befund remediator dispatch has an edit-scope lock open (naming
`src/api.py`), and an Edit arrives targeting an ABSOLUTE path that is not inside the probe
repository at all -- `/tmp/befund-39-outside-repo-differential-target/notes.md`.

## Why this path is genuinely outside the probe

`differential-guard-cases.py` copies this fixture into a fresh temporary directory per run
(`workdir/a/probe`, `workdir/b/probe`), and those temporary directories are always randomly
named subdirectories created by `tempfile.TemporaryDirectory()` -- on this host under
`/var/folders/.../T/tmp<random>/...`, and on a typical Linux CI runner under
`/tmp/tmp<random>/...`. A fixed, hardcoded literal path like
`/tmp/befund-39-outside-repo-differential-target/notes.md` cannot collide with either: it
names a directory the fixture never creates and the runner never creates, so it can never
resolve to somewhere *inside* a probe copy, on any machine this fixture runs on. (A path under
`$HOME` would work just as well for the same reason, but would additionally require the test
environment to actually have a writable `$HOME` set, which a fixed `/tmp` path does not.)

## old=deny (the defect)

At base `b029676`, `guard_target_edit.py` computes `resolved_target =
os.path.realpath(target)` (the absolute-path branch), then compares it only against
`own_output_dir` (no match -- the target isn't under `analysis/befund/`) and then against the
lock's `allowedFiles` (`{"src/api.py"}` resolved) -- no match there either, since the target
resolves to a path entirely outside the repository. Nothing in the old code ever asks whether
the target is inside the repository at all, so "not own_output_dir, not in allowedFiles" falls
through to the generic `remediator-scope-enforcement` deny, exactly as if this were an in-repo
source file the lock simply didn't name.

## new=allow (the fix)

The new containment check runs immediately after the inert/lib-import gates and before the
`own_output_dir` comparison: it resolves the target both lexically (`os.path.normpath`) and via
`os.path.realpath`, and if either disagrees that the target is inside `cwd`, the hook returns
`allow()` without ever reaching `own_output_dir` or `allowedFiles`. This hook exists to gate
writes into the TARGET repository's own source under an open befund lock -- a write to `/tmp`
is not target-repository source, so it is outside every rule this hook enforces, and the fix is
to stop this hook from having an opinion on it at all, not to invent a new one.
