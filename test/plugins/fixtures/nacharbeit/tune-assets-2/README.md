# drift

**Renders contract drift as one static page.**

## Why this exists

Numbers in a terminal scroll away; a page stays.

## What it is not

- Not a dashboard server; one static page per run.

## Install

```
/plugin install drift@fixtures
```

<!-- rrt:auto:start:example-prompts-intro -->
## Example Prompts

Say any of these to Claude Code once the plugin is installed — they're plain-language
prompts, not exact phrasing Claude has to match. Claude routes them to the skill below
by intent.
<!-- rrt:auto:end:example-prompts-intro -->

##### Render the drift report

````prompt
"render the drift report for this run"
````

> Runs `scripts/build_drift_html.py`.

## The report

![The drift report rendered from the committed sample data](drift-viewer-screenshot.jpg)

The demo report is empty by design, so the table renders with no rows. Rebuild it with `python3 scripts/build_drift_html.py scripts/fixtures/sample.json`.

## Verifying a change to this plugin

```bash
python3 plugins/drift/hooks/test_drift_guard.py
```
