---
name: prose-check
description: Checks documentation prose for spelling and grammar problems and reports each with file, line, and a suggestion. Use when the user asks to "check the writing", "proofread the docs", or "lint the prose".
---

# prose-check

Report spelling and grammar problems in Markdown files.

## Steps

1. Find every `*.md` file outside `node_modules/` and `.git/`.
2. Run `vale --output=JSON .` (vale must already be on PATH; if it is not, stop and say so).
3. Map each result to `{file, line, kind, text, suggest}`.

## Output

```json
{"problems": [{"file": "docs/intro.md", "line": 9, "kind": "grammar", "text": "less files", "suggest": "fewer files"}]}
```

Return `{"problems": []}` when vale reports nothing.
