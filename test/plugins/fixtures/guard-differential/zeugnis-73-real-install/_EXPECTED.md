# zeugnis-73-real-install

The anti-loosening half of the issue #73 pair: same probe repository (`analysis/zeugnis/`
present, so the hook is active), but the command genuinely runs an install — `npm install
left-pad` — the exact literal `test/plugins/verify-hooks-deny.py:155-158`'s
`BASH_VIOLATION` probes this hook with, and which must stay denied by any fix to this
guard.

## old=deny and new=deny (the rule the fix must not loosen)

At base `b029676`, the raw-string pattern `\bnpm\s+(install|i|ci|...)\b` matches this
command directly — it really is an `npm install` invocation, not a mention of one, so
the old guard's deny is correct here (unlike `zeugnis-73-grep-mentions-install`, this
case has no false positive to fix).

The fixed guard tokenises the command with `shlex.split` into `['npm', 'install',
'left-pad']`. `argv[0]` is `npm` (a key in `TWO_TOKEN_MUTATORS`) and `argv[1]` is
`install` (a member of `TWO_TOKEN_MUTATORS["npm"]`), so `_matched_mutator` still
matches and the command is still denied. Pairing this with
`zeugnis-73-grep-mentions-install` (deny -> allow) is what proves the fix narrows the
defect rather than loosening the rule the guard exists to enforce: a real install is
refused exactly as before.
