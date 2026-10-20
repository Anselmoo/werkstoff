# tally

**Totals a ledger by record kind.**

## Why this exists

Ledgers are summed by hand and the sums drift.

## What it is not

- Not a ledger writer; it reads.

## Install

```
/plugin install tally@fixtures
```

<!-- rrt:auto:start:example-prompts-intro -->
## Example Prompts

Say any of these to Claude Code once the plugin is installed — they're plain-language
prompts, not exact phrasing Claude has to match. Claude routes them to the skill below
by intent.
<!-- rrt:auto:end:example-prompts-intro -->

##### Total the ledger

````prompt
"total this ledger by kind"
````

> Runs `scripts/tally.py`.


## Verifying a change to this plugin

```bash
python3 plugins/tally/hooks/test_tally_guard.py
```
