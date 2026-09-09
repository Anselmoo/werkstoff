# probe

**Finds broken relative links in a docs tree.**

## Why this exists

Dead links ship because nobody clicks every one.

## What it is not

- Not a spell checker.

## Install

```
/plugin install probe@fixtures
```

<!-- rrt:auto:start:example-prompts-intro -->
## Example Prompts

Say any of these to Claude Code once the plugin is installed — they're plain-language
prompts, not exact phrasing Claude has to match. Claude routes them to the skill below
by intent.
<!-- rrt:auto:end:example-prompts-intro -->

##### Find dead links

````prompt
"do the docs have any dead links"
````

> Runs `scripts/check_links.py`.


## Verifying a change to this plugin

```bash
python3 plugins/probe/hooks/test_probe_guard.py
```
