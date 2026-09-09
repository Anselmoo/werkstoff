---
name: quill-lint
description: "Use when asked to \"lint the prose\", \"check the writing\", \"prose lint\", \"writing check\", \"lint docs prose\", \"style check the docs\", \"proofread\", \"copyedit\", \"check spelling\", \"check grammar\", or \"tighten the text\"."
---

# quill-lint

NEVER produce an unclear report. NEVER be vague. NEVER omit anything. NEVER write a summary the user cannot act on.

## Steps

1. Read `.quill/allowlist.txt` for words the project spells its own way.
2. Apply the spelling pass using the word list from step 5.
3. For grammar you can use `vale`, or `write-good`, or `proselint`, or `languagetool`, or `textlint`.
4. Collect problems.
5. Build the word list from every heading in the docs.
6. Report.

## Output

```json
{"problems": [{"file": "README.md", "line": 3, "kind": "spelling", "text": "recieve", "suggest": "receive"}]}
```

Return `{"problems": []}` when the prose is clean.

## Resources

- `scripts/quill.py` — the spelling pass.
