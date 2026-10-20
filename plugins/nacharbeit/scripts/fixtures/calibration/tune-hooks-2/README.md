# sentry

**Freezes generated files while a review is open.**

## Why this exists

Hand edits to generated files are lost on the next generation run.

## What it is not

- Not a generator; `regen` produces the files. Not `gatekeep`, which freezes on a directory marker rather than a config file.

## Install

```
/plugin install sentry@fixtures
```

<!-- rrt:auto:start:example-prompts-intro -->
## Example Prompts

Say any of these to Claude Code once the plugin is installed — they're plain-language
prompts, not exact phrasing Claude has to match. Claude routes them to the skill below
by intent.
<!-- rrt:auto:end:example-prompts-intro -->

##### Freeze generated files

````prompt
"freeze the generated docs while this review is open"
````

> Creates the marker so the hook starts denying writes to `*.generated.md`.

## Hooks

See the source for what the hook does and when.

## Verifying a change to this plugin

```bash
python3 plugins/sentry/hooks/test_sentry_guard.py
```
