# quill

**Reports passive voice and nominalisations in prose.**

## Why this exists

Prose weakens sentence by sentence.

## What it is not

- Not `prose-check`, which judges tone; quill reports two constructs.

## Install

```
/plugin install quill@fixtures
```

<!-- rrt:auto:start:example-prompts-intro -->
## Example Prompts

Say any of these to Claude Code once the plugin is installed — they're plain-language
prompts, not exact phrasing Claude has to match. Claude routes them to the skill below
by intent.
<!-- rrt:auto:end:example-prompts-intro -->

##### Lint the prose

````prompt
"tighten the prose in these docs"
````

> Triggers `quill-lint`.


## Verifying a change to this plugin

```bash
python3 plugins/quill/hooks/test_quill_guard.py
```
