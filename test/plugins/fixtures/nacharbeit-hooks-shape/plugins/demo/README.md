# demo

**Freezes generated files while a review is open.**

## Why this exists

Hand edits to generated files are lost on the next generation run.

## What it is not

- Not a generator.

## Install

```
/plugin install demo@fixtures
```

<!-- rrt:auto:start:example-prompts-intro -->
## Example Prompts

Say any of these to Claude Code once the plugin is installed — they're plain-language
prompts, not exact phrasing Claude has to match. Claude routes them to the skill below
by intent.
<!-- rrt:auto:end:example-prompts-intro -->

##### What drifted

````prompt
"which generated files drifted"
````

> Triggers `demo-check`.

## Hooks

One `PreToolUse` hook; inert until `.demo/` exists. Escape hatch `DEMO_DISABLE_GUARD=1`.

## Verifying a change to this plugin

```bash
python3 plugins/demo/hooks/test_demo_guard.py
```
