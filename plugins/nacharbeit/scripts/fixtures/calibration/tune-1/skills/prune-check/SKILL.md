---
name: prune-check
description: Checks a repository's dependency tree for packages that are declared but never imported and reports them. Use when the user asks to "find unused packages", "check for dead dependencies", or "audit the manifest".
---

# prune-check

Read the manifest, grep for each declared package, report the ones with zero import hits.

## Steps

1. Read the manifest and list declared packages.
2. Grep the source tree for each package.
3. Report packages with zero hits.

## Output

```json
{"unused": [{"package": "left-pad", "manifest_line": 14}]}
```

When nothing is unused, return `{"unused": []}`.
