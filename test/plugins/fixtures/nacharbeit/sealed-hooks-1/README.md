# lockstep

**Denies a write that runs ahead of a declared beat.**

## Why this exists

A beat order written as prose is skipped one run in three.

## What it is not

- Not `takt`, which reads `.claude/takt.local.md`; lockstep reads its own beats file.

## Install

```
/plugin install lockstep@fixtures
```

<!-- rrt:auto:start:example-prompts-intro -->
## Example Prompts

Say any of these to Claude Code once the plugin is installed — they're plain-language
prompts, not exact phrasing Claude has to match. Claude routes them to the skill below
by intent.
<!-- rrt:auto:end:example-prompts-intro -->

##### Declare the beats

````prompt
"set up lockstep so tests can't be written before the contract is settled"
````

> Writes `.lockstep/beats.json`; the hook then denies a write that runs ahead of a beat.

## Hooks

One `PreToolUse` hook, `type: "command"`, matching `Write|Edit|MultiEdit`.

- **Inert** until `.lockstep/beats.json` exists.
- **Escape hatch**: `LOCKSTEP_DISABLE_GUARD=1`.

## Testing

```bash
python3 test/plugins/verify-hooks-deny.py plugins/lockstep
```

## Verifying a change to this plugin

```bash
python3 plugins/lockstep/hooks/test_lockstep_guard.py
```
