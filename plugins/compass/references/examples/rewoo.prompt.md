---
name: rewoo-plan-execute-solve
description: >-
  Completes a multi-lookup research task using ReWOO (Reasoning WithOut
  Observation), where the full tool-call plan is generated upfront in one
  pass, executed without re-reasoning between calls, then synthesized.
  Use when tool calls are expensive/slow/rate-limited and the plan
  doesn't need to adapt after each individual result.
---

You are a research planner. Generate a complete plan of tool calls needed
to answer the task below, execute every call in the plan without
re-reasoning between them, then synthesize a final answer.

## Available tools

- `search(query: str)` — returns a list of web search result snippets
- `fetch_url(url: str)` — returns full page text
- `compare(items: list[str], criteria: str)` — returns a comparison table

## Task

{{TASK_DESCRIPTION}}

## Format

```
Plan:
#E1 = <tool>(<arguments>)
#E2 = <tool>(<arguments, may reference #E1>)
...

Execute:
#E1 result: <what the tool actually returned>
#E2 result: <what the tool actually returned>
...

Solve:
<final answer that directly answers the task, citing which #E results it used>
```

## Example task trace

**Task:** Compare the release dates and headline features of two
competing database engines.

```
Plan:
#E1 = search("PostgreSQL 17 release date headline features")
#E2 = search("MySQL 9 release date headline features")
#E3 = compare(["#E1", "#E2"], "release date, headline features")

Execute:
#E1 result: PostgreSQL 17 released September 2024 — incremental backup, JSON_TABLE, faster vacuum.
#E2 result: MySQL 9.0 (Innovation release) — vector data type support, improved replication.
#E3 result: | | Release | Headline feature |
|---|---|---|
| PostgreSQL 17 | Sep 2024 | Incremental backup, JSON_TABLE |
| MySQL 9.0 | 2024 | Vector data type, replication improvements |

Solve:
PostgreSQL 17 (Sep 2024) headlines incremental backup and JSON_TABLE; MySQL 9.0 headlines native vector-type support and replication improvements — based on #E1/#E2/#E3.
```

## Why this technique

The two lookups are independent — neither result changes what the other
search should be. Planning both calls upfront in one pass, rather than
reasoning between them, avoids paying an interleaved-reasoning cost for
zero adaptive benefit.

## When to escalate

If a later step's tool call genuinely needs to change based on what an
earlier step returned (the plan can't be fully specified upfront) →
switch to ReAct or ART, which interleave reasoning between calls instead
of committing to the full plan first.
