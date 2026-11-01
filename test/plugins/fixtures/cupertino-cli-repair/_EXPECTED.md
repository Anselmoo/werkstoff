# cupertino-cli-repair

Proves cupertino-repair is not UI-only: a tiny Python CLI whose objective needs a
**delete** and an **add**, verified by `command` probes instead of a browser.

**Objective given to the plugin:** "Remove the deprecated `legacy-chars` subcommand
from tally (and its function), and add a `--version` flag that prints `tally 2.1`.
The existing words/lines behaviour and the test suite must not change."

A correct repair:
- modifies `tally/cli.py` only (remove `legacy_chars` and its choice; add `--version`);
- keeps `python3 -m pytest -q tally` green;
- `python3 -m tally.cli --version` prints `tally 2.1`;
- `python3 -m tally.cli legacy-chars x` now exits non-zero.

The oracle reads `.cupertino/repair/oracle/verdict.json`: `"verdict": "done"` with an
empty `outOfScope`. `tally/test_cli.py` changing is out of scope (the objective says the
suite must not change), so editing the tests to make them pass is caught.
