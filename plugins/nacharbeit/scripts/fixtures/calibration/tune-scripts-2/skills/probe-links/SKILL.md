---
name: probe-links
description: "Finds broken relative links in a docs tree and lists them by page. Use when the user asks whether the docs have dead links."
---

Find the dead links.

## Steps

1. **Locate the docs root** the user names, or `docs/`.
2. **Check the links** — see scripts/check_links.py for details.
3. **Report** every `page: target` line, grouped by page.

## Resources

- `scripts/check_links.py`

