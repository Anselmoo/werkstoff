# tether

**Ties each test to the requirement it covers.**

## Why this exists

Requirements without a test go unnoticed.

## What it is not

- Not a test runner; it maps.

## Install

```
/plugin install tether@fixtures
```

<!-- rrt:auto:start:example-prompts-intro -->
## Example Prompts

Say any of these to Claude Code once the plugin is installed — they're plain-language
prompts, not exact phrasing Claude has to match. Claude routes them to the skill below
by intent.
<!-- rrt:auto:end:example-prompts-intro -->

##### Map coverage

````prompt
"which requirements have no test"
````

> Triggers `tether-map`.


## Verifying a change to this plugin

```bash
python3 plugins/tether/hooks/test_tether_guard.py
```
