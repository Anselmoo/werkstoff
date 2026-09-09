# gauge

**Renders doctrine violations as one static page.**

## Why this exists

Numbers in a terminal scroll away; a page stays.

## What it is not

- Not a dashboard server; one static page per run.

## Install

```
/plugin install gauge@fixtures
```

<!-- rrt:auto:start:example-prompts-intro -->
## Example Prompts

Say any of these to Claude Code once the plugin is installed — they're plain-language
prompts, not exact phrasing Claude has to match. Claude routes them to the skill below
by intent.
<!-- rrt:auto:end:example-prompts-intro -->

##### Render the gauge report

````prompt
"render the gauge report for this run"
````

> Runs `scripts/build_gauge_html.py`.

## The report

![The gauge report rendered from the committed sample data](gauge-viewer-screenshot.jpg)

The sample data carries one blocking violation, the case the page exists to show. Rebuild it with `python3 scripts/build_gauge_html.py scripts/fixtures/sample.json`.

## Verifying a change to this plugin

```bash
python3 plugins/gauge/hooks/test_gauge_guard.py
```
