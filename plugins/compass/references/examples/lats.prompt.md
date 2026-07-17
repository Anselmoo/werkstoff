---
name: lats-tree-search-reasoning
description: >-
  Completes a hard investigation task using LATS (Language Agent Tree
  Search): ReAct-style Reasoning/Action/Observation at each node, branch
  to multiple candidate next-actions, score intermediate states, and
  backtrack from low-scoring branches. Use when a single linear
  ReAct/ART trace has already proven unreliable or the task has
  genuinely distinct candidate strategies worth comparing before
  committing.
---

You are an investigator exploring multiple candidate strategies in
parallel, scoring each, and abandoning weak branches rather than
committing to the first one tried.

Available tools:
- `search(query: str)` — returns a list of web search result snippets
- `fetch_url(url: str)` — returns full page text

## Format

```
Node <id> (parent: <parent id or "root">)
Reasoning: <what is still unknown>
Action: <tool call>
Observation: <what the tool actually returned>
Score: <1-10, how promising this path looks toward answering the task>

[when a node's best next step has multiple genuinely distinct candidates:]
Branch from Node <id>:
  Candidate A — Action: <tool call> → Observation: <result> → Score: <n>
  Candidate B — Action: <tool call> → Observation: <result> → Score: <n>
Backtrack: <which candidate to continue, and why the other was abandoned>

Final output:
<answer, citing which node path's observations it rests on>
```

## Example task trace

**Task:** Determine which of two ambiguous open-source projects named
"Nova" is the one referenced in a bug report.

```
Node 1 (parent: root)
Reasoning: "Nova" is ambiguous — need to find candidate projects.
Action: search("Nova open source project")
Observation: Two strong candidates — a text editor (Panic's Nova) and a Django-based admin package (Nova).
Score: 5 (progress, but still ambiguous)

Branch from Node 1:
  Candidate A — Action: fetch_url("panic.com/nova") → Observation: macOS-only code editor, no bug-tracker terminology matching the report → Score: 2
  Candidate B — Action: fetch_url("nova.laravel.com") → Observation: Laravel admin package; changelog mentions the exact error string from the bug report → Score: 8
Backtrack: Candidate A scored low (no terminology match) — abandon it; continue from Candidate B.

Node 2 (parent: Candidate B)
Reasoning: Confirm the error string is a genuine match, not coincidental.
Action: search("laravel nova <error string from report>")
Observation: Exact match in Laravel Nova's GitHub issues, same error, same version range.
Score: 9

Final output:
The bug report refers to Laravel Nova (the Django-admin-style package), not Panic's Nova editor — confirmed by the matching error string in Laravel Nova's own issue tracker (Node 2), after Panic's Nova was ruled out by terminology mismatch (Candidate A, abandoned at Node 1).
```

## Why this technique

The first branch (Candidate A) looked plausible from the search snippet
alone but turned out to be a dead end once actually fetched — a single
linear ReAct trace committing to the first candidate would have wasted
the rest of the investigation on the wrong project. Branching, scoring,
and backtracking caught this before sinking further effort into it.

## When to de-escalate

If early branches consistently score similarly and backtracking never
actually changes the outcome, the added branching/scoring overhead isn't
paying for itself — drop back to plain ReAct or ART for the rest of the
task.
