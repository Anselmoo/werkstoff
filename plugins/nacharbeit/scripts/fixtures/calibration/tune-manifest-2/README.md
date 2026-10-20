# ledgerly

**Reconciles a ledger directory against its index and reports the differences.**

## Why this exists

Yesterday I ran this on my laptop and it took 4 minutes on the big ledger, then I found the index had been stale since March; this README is the notes I took while fixing that.

## What it is not

- Not `tally`, which sums by kind; ledgerly compares records to the index.

## Install

```
/plugin install ledgerly@fixtures
```

<!-- rrt:auto:start:example-prompts-intro -->
## Example Prompts

Say any of these to Claude Code once the plugin is installed — they're plain-language
prompts, not exact phrasing Claude has to match. Claude routes them to the skill below
by intent.
<!-- rrt:auto:end:example-prompts-intro -->

##### Reconcile the ledger

````prompt
"does the ledger agree with its index"
````

> Triggers `ledgerly-reconcile`.


## Verifying a change to this plugin

```bash
python3 plugins/ledgerly/hooks/test_ledgerly_guard.py
```
