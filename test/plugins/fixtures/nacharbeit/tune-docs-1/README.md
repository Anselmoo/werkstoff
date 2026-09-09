# wick

**Reports Markdown formatting violations against a style file.**

## Why this exists

Style drifts one commit at a time.

## What it is not

- Not a formatter; it reports.

## Install

```
/plugin install wick@fixtures
```

<!-- rrt:auto:start:example-prompts-intro -->
## Example Prompts

Say any of these to Claude Code once the plugin is installed — they're plain-language
prompts, not exact phrasing Claude has to match. Claude routes them to the skill below
by intent.
<!-- rrt:auto:end:example-prompts-intro -->

##### Check the docs

````prompt
"do the docs follow our style file"
````

> Triggers `wick-check`.


## Verifying a change to this plugin

```bash
python3 plugins/wick/hooks/test_wick_guard.py
```
