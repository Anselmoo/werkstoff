# weigh

**Fails the build when a bundle is over its weight budget.**

## Why this exists

Bundles grow one dependency at a time.

## What it is not

- Not a bundler.

## Install

```
/plugin install weigh@fixtures
```

<!-- rrt:auto:start:example-prompts-intro -->
## Example Prompts

Say any of these to Claude Code once the plugin is installed — they're plain-language
prompts, not exact phrasing Claude has to match. Claude routes them to the skill below
by intent.
<!-- rrt:auto:end:example-prompts-intro -->

##### Weigh the bundles

````prompt
"are the bundles within budget"
````

> Runs `scripts/weigh_lint.py`.


## Verifying a change to this plugin

```bash
python3 plugins/weigh/hooks/test_weigh_guard.py
```
