# Start here

Twelve plugins is too many to pick from cold. This page is the shortest path from an
empty session to a workflow that actually fires.

## 1. Install the three layers

werkstoff supplies the inspectors. Two other marketplaces supply the process discipline
and the named reviewer agents, and most recipes here assume all three.

```
/plugin marketplace add Anselmoo/werkstoff
/plugin install arbeitsplan@werkstoff
/plugin install superpowers@claude-plugins-official
/plugin install pr-review-toolkit@claude-plugins-official
```

Install the rest per workflow — each one names what it needs, and nothing here needs all
twelve. `arbeitsplan` goes first only because it carries the front door below.

## 2. Ask which workflow fits

```prompt
which werkstoff workflow fits what I am about to do, and what should I run first?
```

That reaches `arbeitsplan-start`, which reads the [approved workflows](/plugins/references/approved-workflows)
and answers with a mode, an install list and an opening prompt. It recommends only: it
never installs, dispatches or edits, and "no fit" is one of its answers.

**Measured caveat, because this page will not pretend otherwise:** that skill fired in
1 of 4 recorded runs, and only on sonnet — see [the routing evidence](/examples/routing).
On a cheap model it mostly does not trigger, and naming the skill outright works better:

```prompt
use arbeitsplan-start: I want to add a feature to an unfamiliar repo
```

## 3. Pick the permission mode on purpose

The mode decides whether the work can happen at all, and the wrong one wastes a whole
session. [Permission modes](/start/permission-modes) has the detail and the evidence; the
short version:

| what you are doing | mode |
|---|---|
| reading, mapping, planning | `plan` |
| editing, fixing, hardening | Manual (`default`) or `acceptEdits` |
| long autonomous stretches you trust | `auto` |

## 4. Know what lands in your repo

Every werkstoff plugin that writes, writes somewhere predictable, and several arm a
`PreToolUse` guard once they do. A denial from one is that plugin doing its job, not a
malfunction — [composition hazards](/orchestration/references/hazards) covers what
collides when several share a session.

## Where to go next

- [Approved workflows](/plugins/references/approved-workflows) — the four, with their modes, installs and opening prompts
- [Measured examples](/examples/) — the recorded runs behind every claim on this page
- [Prompt catalog](/catalog/) — task-indexed recipes, beyond the four
- [Orchestration overview](/orchestration/) — how the three layers compose
- [Glossary](/glossary) — beat, stage, wire, leaf, orchestrator
