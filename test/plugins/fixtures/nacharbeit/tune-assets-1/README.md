# burn

**Renders a burndown of open findings as one static page.**

## Why this exists

Numbers in a terminal scroll away; a page stays.

## What it is not

- Not a dashboard server; one static page per run.

## Install

```
/plugin install burn@fixtures
```

<!-- rrt:auto:start:example-prompts-intro -->
## Example Prompts

Say any of these to Claude Code once the plugin is installed — they're plain-language
prompts, not exact phrasing Claude has to match. Claude routes them to the skill below
by intent.
<!-- rrt:auto:end:example-prompts-intro -->

##### Render the burn report

````prompt
"render the burn report for this run"
````

> Runs `scripts/build_burn_html.py`.

## The report

![The burn report rendered from the committed sample data](burn-viewer-screenshot.jpg)

The sample data shows a clean run with nothing left to burn down, so the page renders its happy path. Rebuild it with `python3 scripts/build_burn_html.py scripts/fixtures/sample.json`.

## Verifying a change to this plugin

```bash
python3 plugins/burn/hooks/test_burn_guard.py
```
