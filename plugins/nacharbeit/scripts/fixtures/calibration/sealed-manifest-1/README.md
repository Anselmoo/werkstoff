# spool

**Queues long-running checks and reports results as they finish.**

## Why this exists

Waiting for the slowest check hides the fast ones' results.

## What it is not

- Not a scheduler.

## Install

```
/plugin install spool@fixtures
```

<!-- rrt:auto:start:example-prompts-intro -->
## Example Prompts

Say any of these to Claude Code once the plugin is installed — they're plain-language
prompts, not exact phrasing Claude has to match. Claude routes them to the skill below
by intent.
<!-- rrt:auto:end:example-prompts-intro -->

##### Run the checks

````prompt
"run all the checks and show me results as they come in"
````

> Triggers `andon-loop`.

##### A note

````prompt
"how did the last run go"
````

> Last Tuesday the queue got stuck behind a 40-minute check and I had to kill it by hand — triggers `spool-run`.


## Verifying a change to this plugin

```bash
python3 plugins/spool/hooks/test_spool_guard.py
```
