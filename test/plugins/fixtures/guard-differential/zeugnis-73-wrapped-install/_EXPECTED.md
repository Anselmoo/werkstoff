# zeugnis-73-wrapped-install

The anti-loosening half the pair was missing until the coordinator's regression
report: `sudo npm install left-pad` — a real install, wrapped in an ordinary,
non-adversarial `sudo` prefix a cooperative model writes routinely. Same probe
repository (`analysis/zeugnis/` present) as the other two `zeugnis-73-*` cases.

## Why the bare-command case (`zeugnis-73-real-install`) could not catch this

`zeugnis-73-real-install` proves `npm install left-pad` (bare, argv[0] == "npm")
is still denied after the argv rewrite. It cannot say anything about what happens
when a wrapper sits in front of the real command, because there is no wrapper in
it — the same reason the first version of this fix shipped only a bare-command
pair and missed the regression this case exists to pin down.

## old=deny and new=deny (the rule the fix must not loosen)

At base `b029676`, the raw-string pattern `\bnpm\s+(install|...)\b` matches this
command directly: `re.search` does not care what precedes "npm install" in the
string, so `sudo ` in front changes nothing and the old guard denies exactly as
it does for the bare form.

The fixed guard tokenises the command with `shlex.split` into `['sudo', 'npm',
'install', 'left-pad']`. Anchoring argv[0] to `npm` would miss this — `argv[0]`
is `sudo`, not a key in `TWO_TOKEN_MUTATORS` — which is exactly the regression:
argv-based matching, alone, lost the "does not care what comes first" property
the old substring search had for free. `_skip_wrappers` strips the leading
`sudo` (a `WRAPPER_COMMANDS` entry, no value-taking flag present here) before
`_matched_mutator` looks at argv[0]/argv[1], landing on `npm install` and
denying. Pairing this with `zeugnis-73-grep-mentions-install` (deny -> allow)
and `zeugnis-73-real-install` (deny -> deny, bare form) is what proves the fix
narrows the original defect without reopening a new one via any wrapper a
cooperative model would plausibly write.
