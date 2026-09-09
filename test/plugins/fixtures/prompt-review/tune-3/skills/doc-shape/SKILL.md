---
name: doc-shape
description: "Use when the user says \"check the docs\", \"review documentation\", \"docs look off\", \"is the README okay\", \"documentation review\", \"look at the docs\", \"README check\", \"docs audit\", \"check README\", \"review README\", \"doc review\", or \"docs pass\"."
context: fork
---

# doc-shape

Status: DRAFT — update this line when the team approves the checklist.

Documentation in a repository is written in Markdown, which is a lightweight markup language where headings start with `#`, lists with `-`, and code is fenced with three backticks. JSON, which stands for JavaScript Object Notation, is a text format for structured data made of objects in braces and arrays in brackets. These formats are what this skill reads.

The reviewer should open the README and every file under docs/, then check each heading level is at most one deeper than its parent, then check every relative link resolves, then check every fenced code block declares a language, then collect the problems, then write them up. If a link points at a file that also has a problem, then delete it.

## Heading rules

| level | allowed parents | max length | notes |
|---|---|---|---|
| h1 | none | 60 | exactly one per file |
| h2 | h1 | 70 | |
| h3 | h2 | 80 | |
| h4 | h3 | 80 | avoid |
| h5 | h4 | 80 | avoid |
| h6 | h5 | 80 | never |

## Link rules

| kind | check |
|---|---|
| relative | target exists |
| anchor | heading exists in target |
| absolute http | not checked |

## Fence rules

| rule | detail |
|---|---|
| language | every fence names a language |
| length | fences over 80 lines get a note |

## Output

```
<problem-kind>: <file>:<line> — <detail>
```

## Resources

- [`references/rules.md`](references/rules.md) — the full heading, link, and fence rule tables.
