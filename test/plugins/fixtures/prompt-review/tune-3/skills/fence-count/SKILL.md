---
name: fence-count
description: Counts fenced code blocks per language across a repository's Markdown files and prints a frequency table. Use when the user asks "which languages do the docs show", "count code examples", or "how many code blocks are there".
---

# fence-count

Count opening code fences by declared language.

## Steps

1. Find every `*.md` file under the repository, excluding `node_modules/` and `.git/`.
2. For each opening fence (a line starting with three backticks), take the word after the backticks as the language; an empty word is `(none)`.
3. Print a table sorted by count, descending.

## Output

```
python   14
bash      9
(none)    3
```

If no Markdown files exist, return exactly: `No Markdown files.`
