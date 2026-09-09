---
name: tag-list
description: Lists a repository's git tags newest-first with their dates, as a plain table. Use when the user asks "what tags exist", "show me the release tags", or "when was the last tag".
---

# tag-list

Print the repository's tags, newest first, with the tagging date.

## Steps

1. Run `git tag --sort=-creatordate --format='%(refname:short)  %(creatordate:short)'`.
2. Print the output as a two-column table.

## Output

```
v1.4.0  2025-06-02
v1.3.1  2025-04-18
```

If the repository has no tags, return exactly: `No tags.`
