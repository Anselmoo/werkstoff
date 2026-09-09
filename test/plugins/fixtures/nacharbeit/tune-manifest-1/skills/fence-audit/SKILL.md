---
name: fence-audit
description: "Lists every Markdown code fence without a language tag, by file and line. Use when the user asks which fences are untagged. Read-only; never edits a file."
---

List untagged fences.

## Steps

1. **Scan** every `*.md` under the named directory.
2. **Report** `file:line` for each fence whose opening line is bare ```` ``` ````.

