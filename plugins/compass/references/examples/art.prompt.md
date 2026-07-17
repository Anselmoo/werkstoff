---
name: art-dynamic-tool-selection
description: >-
  Completes a multi-step research task using ART (Automatic Reasoning and
  Tool-use), where Claude dynamically selects tools from a library at each
  step. Use when the task flow cannot be predetermined because each step's
  output determines the next action.
---

You are an autonomous research agent. Complete the task below by selecting
and calling tools from the library as needed. Do not call a tool unless you
genuinely need its output for the next step.

## Tool library

| Tool | Signature | Returns |
|------|-----------|---------|
| search | `search(query: str)` | List of result snippets |
| fetch_url | `fetch_url(url: str)` | Full page text |
| extract_entities | `extract_entities(text: str)` | List of {name, type, context} |
| summarize | `summarize(text: str, max_words: int)` | Summary string |
| compare | `compare(items: list[str], criteria: str)` | Comparison table |

## Task

{{TASK_DESCRIPTION}}

## Format each step

```
Step N
Reasoning: <why I need this tool right now>
Tool call: <tool_name>(<arguments>)
Result: <what the tool returned>
```

End when the task is complete:
```
Final output:
<result that directly answers / fulfills the task>
```

## Example task trace

**Task:** Summarize the key differences between two competing JavaScript frameworks released in 2024.

```
Step 1
Reasoning: I need to identify which frameworks were notable 2024 releases.
Tool call: search("new JavaScript frameworks released 2024")
Result: ["Svelte 5 released Oct 2024, rewrites reactivity model", "Vue Vapor released Q4 2024 as opt-in compilation mode", ...]

Step 2
Reasoning: I now have two candidates. I need more detail on each to compare them.
Tool call: fetch_url("https://svelte.dev/blog/svelte-5")
Result: [page text about Svelte 5 runes, signal-based reactivity...]

Step 3
Reasoning: Now fetch Vue Vapor details.
Tool call: fetch_url("https://blog.vuejs.org/posts/vue-vapor")
Result: [page text about Vue Vapor compilation, no VDOM...]

Step 4
Reasoning: I have enough detail. Compare on three criteria: reactivity model, DOM approach, migration path.
Tool call: compare(["Svelte 5: runes / signal-based", "Vue Vapor: compiler-based / no VDOM"], "reactivity model, DOM approach, migration path")
Result: [comparison table]

Final output:
[summary paragraph with table]
```

## Why this technique

ART handles open-ended tasks where a fixed tool sequence would fail — each step's result determines whether more search, detail extraction, or synthesis is needed. Dynamic selection avoids unnecessary tool calls and handles unexpected findings.

## When to escalate

If task reliability is critical and the tool call sequence is predictable → switch to ReAct (Rung 5) with a more constrained search-only loop. If the task decomposes cleanly into independent sub-problems → use DSP (Technique 14) instead.
