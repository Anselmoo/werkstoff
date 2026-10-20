# gatekeep

**Freezes generated files while a review is open — the write is denied, not warned about.**

## Why this exists

A generated file edited by hand during a review is overwritten by the next generation run, and nobody notices.

## What it is not

- Not a generator. It only refuses writes; `regen` produces the files.

## Install

```
/plugin install gatekeep@fixtures
```

<!-- rrt:auto:start:example-prompts-intro -->
## Example Prompts

Say any of these to Claude Code once the plugin is installed — they're plain-language
prompts, not exact phrasing Claude has to match. Claude routes them to the skill below
by intent.
<!-- rrt:auto:end:example-prompts-intro -->

##### Freeze generated files during a review

````prompt
"freeze the generated docs while this review is open"
````

> Creates `.gatekeep/` so the hook starts denying writes to `*.generated.md`.

## Hooks

One `PreToolUse` hook, `type: "command"`, matching `Write|Edit|MultiEdit`.

- **Inert** until `.gatekeep/` exists.
- **Escape hatch**: `GATEKEEP_DISABLE_GUARD=1`.

## Testing

```bash
python3 test/plugins/verify-hooks-deny.py plugins/gatekeep
```

## Verifying a change to this plugin

```bash
python3 plugins/gatekeep/hooks/test_gatekeep_guard.py
```
