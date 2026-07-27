# Seeded defects: a CLI that violates cli-scaffold's own doctrine

Stripped from the copied fixture by `test/plugins/run.sh` — the plugin under
test must never see this file.

## Why this shape rather than "generate a CLI and inspect it"

A generation fixture cannot be scored reliably: the produced filenames, module
layout and language idioms vary per run, so the oracle would end up matching
whatever the run *said* it did rather than what it produced — the exact defect
that made `broken-wire-blocks-advance` void. Handing the plugin an existing CLI
with known violations makes the correct answer fixed and checkable.

## The violations, and the rule each breaks

1. **core-library-isolation** — `src/widget/core/logic.py:1` does `import click`
   and calls `click.echo()` at line 7. The core/library layer must contain no
   import of CLI-framework code; that coupling makes the logic unusable from a
   library caller, a test, or a different front end.

2. **exit-code-usage-error** — `src/widget/cli.py:14` exits **1** on a missing
   required option. The frozen contract reserves 1 for a *runtime* error and
   **2** for a usage error. A caller cannot distinguish "you invoked me wrong"
   from "the operation failed".

3. **no-color-honored** — `src/widget/cli.py:17` emits a hardcoded ANSI escape
   (`\033[32m`) with no `NO_COLOR` check.

4. **snapshot-test-help-required** — `tests/` contains one logic test and no
   test that captures `--help` output against a stored snapshot, so the CLI's
   user-facing surface can drift silently.

PASS = reports the core/CLI-framework coupling AND the wrong usage exit code.
       Both are unambiguous, single-location, and stated as MUST rules.
FAIL = reports neither, or only generic style observations.

Violations 3 and 4 are deliberately NOT required by the oracle. They are real
and a good implementation should find them, but requiring four findings would
make the case fail on thoroughness rather than on the doctrine check itself.
