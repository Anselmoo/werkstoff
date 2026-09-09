# hook-violation fixture for nacharbeit

`analysis/nacharbeit/fix_scope.json` is present, so a nacharbeit fix pass is in
flight in this repository. The lock authorizes exactly one file,
`plugins/demo/skills/one/SKILL.md` (haiku tier).

The probe target is `plugins/demo/agents/other.md` (via `_TARGET`), which the lock
does not name. The DEFAULT probe target ("src/api.py") is not in the lock either
and would also be denied, but the override keeps the scenario the one the guard
exists for: a remediator editing a plugin file its dispatch was not given.

PASS = exit 2, reason cites "not in the fix scope".
FAIL = exit 0 (an edit outside the fix scope would land during the pass).

The inert probe runs in an empty directory with no lock, where the guard must allow.
