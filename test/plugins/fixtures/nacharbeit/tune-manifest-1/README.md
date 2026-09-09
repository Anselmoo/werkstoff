# fence

**Reports every Markdown code fence that has no language tag.**

## Why this exists

Untagged fences render without highlighting and nobody notices until a reader does.

## What it is not

Not many things.

## Install

```
/plugin install fence@fixtures
```

<!-- rrt:auto:start:example-prompts-intro -->
## Example Prompts

Say any of these to Claude Code once the plugin is installed — they're plain-language
prompts, not exact phrasing Claude has to match. Claude routes them to the skill below
by intent.
<!-- rrt:auto:end:example-prompts-intro -->

##### Find untagged fences

````prompt
"which code fences in the docs have no language tag"
````

> Triggers `confab-dependency-audit`.


## Verifying a change to this plugin

```bash
python3 plugins/fence/hooks/test_fence_guard.py
```
