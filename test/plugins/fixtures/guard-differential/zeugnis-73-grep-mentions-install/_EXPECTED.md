# zeugnis-73-grep-mentions-install

Reproduces issue #73: the probe repository has `analysis/zeugnis/` (so the hook is
active), and the Bash command is a read-only `grep` whose *pattern argument* happens
to contain the two words `pip install` — because `docs/setup.md` documents that
command, it does not run it.

## old=deny (the defect)

At base `b029676`, `guard_bash_scope.py` matched every `DANGEROUS_PATTERNS` entry
with `re.search` against the **raw, untokenised command string** (`:85-88` at that
commit). The compiled pattern for `pip install` (`\bpip3?\s+install\b`,
case-insensitive) has no notion of "this is a quoted grep argument, not an
invocation" — it matches the substring `pip install` wherever it sits in the string,
including inside `"pip install"` here. The command never runs `pip`; the old guard
denied it anyway.

## new=allow (the fix)

The fixed guard tokenises the command with `shlex.split` before deciding anything.
`shlex.split('grep -rn "pip install" docs/")` yields `['grep', '-rn', 'pip install',
'docs/']` — the quoted `pip install` stays a **single argv element**, not two
adjacent words. The mutator check only fires on `argv[0]` (optionally `argv[1]`) of
each shell segment; here `argv[0]` is `grep`, which is not in `TWO_TOKEN_MUTATORS`,
so nothing matches and the command is allowed. Quote-awareness is exactly what the
old raw-string search lacked and what makes "mentions" and "executes" distinguishable.
