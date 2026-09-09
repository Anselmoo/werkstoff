---
name: demo-check
description: "Reports which generated files changed since the last generation run. Use when the user asks what drifted. Read-only; never edits a file."
---

Report drifted generated files.

## Steps

1. **List** every `*.generated.md`.
2. **Report** the ones whose mtime is newer than `.demo/last-run`.
