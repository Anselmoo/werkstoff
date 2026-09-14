---
name: arbeitsplan-start
description: "Names which of four approved workflows fits a stated task, the plugins to install for it, and the permission mode to run it in — and says plainly when none of the four fits. Use when the user asks where to start, which workflow or plugin combination applies, whether to use plan mode or auto mode for something, what to install before beginning, or how to combine werkstoff's plugins for a build, an unfamiliar-repo read, a bug fix, or a UI/plugin review. Recommend-only — it never installs anything, writes workflow.json, or changes permission mode itself."
argument-hint: "<what you're about to do>"
---

# Where to start

A new session asks "which workflow", "plan or auto mode", or "what do I install" and gets a
guess instead of an answer grounded in what has actually been measured about this repository.
This skill answers from one frozen list of four workflows and refuses to invent a fifth.

## Steps

1. **Read `references/approved-workflows.md` in full, every time.** It is the single source
   for the four workflows, the permission-mode facts, and the measured plan-mode hazard.
   Never answer from memory, even on a repeat question in the same session — the reference may
   have changed since it was last read.
2. **Match the stated task to exactly one of the four workflows** — build a feature, understand
   an unfamiliar repo, fix a bug or harden a repo, design a UI or review a plugin. If the task
   does not fit any of the four, say so plainly and stop; "no fit" is a real answer, not a
   failure to find one.
3. **Check the session's current skill/plugin listing** for whatever that workflow's Install
   field names. For each plugin not present, name it exactly and give its exact install command
   from the reference's "Install commands" section — never a paraphrase.
4. **State the Mode field verbatim** from the matched workflow's table row, and flag the
   measured plan-mode-plus-run-scope-lock hazard when the recommended mode is `plan` and an
   arbeitsplan run might already be open.
5. **Report the Writes-to-repo and Hooks-that-may-deny fields verbatim**, and report the
   Evidence field exactly as written — most of these currently read "pending"; report that
   plainly rather than implying a measurement exists.

## Rules

- Never recommend a workflow, a plugin, or a permission mode absent from
  `references/approved-workflows.md`. The reference is the only source of these facts.
- Never invent a fifth workflow to force a fit. "No fit — this doesn't match any of the four"
  is a valid, complete answer.
- Never upgrade a `pending` Evidence line to sound measured. Quote it as written.
- This skill is read-only: it recommends a workflow and a mode, and never installs a plugin,
  writes `workflow.json`, opens a run, or changes the session's permission mode itself. Those
  actions belong to the workflow's own plugins, not to this one.

## Output format

```
arbeitsplan start — "there's a bug in the rate limiter and I want to fix it properly"

workflow   C. Fix a bug, or harden a repo
mode       Manual or acceptEdits, NOT plan — the work is edits, and a ledger lock is involved
install    superpowers (present) + andon@werkstoff (MISSING -> /plugin install andon@werkstoff)
prompt     "find the root cause before changing anything, then prove the fix"
writes     analysis/andon/ledger/**
hook       andon's PreToolUse denies every write outside the ledger while it's in a stop state
evidence   pending — measured run not yet recorded
```

A "no fit" answer looks like this instead of forcing one of the four above:

```
arbeitsplan start — "explain what this function does"

no fit — none of the four approved workflows matches a plain read-and-explain request with
no artifact and no repo change. Ask the question directly, or use compass@werkstoff if the
answer needs grounded, cited reasoning rather than a workflow.
```

## Resources

- `references/approved-workflows.md` — the four workflows (Mode, Install, Opening prompt,
  Writes to repo, Hooks that may deny, Evidence), the permission-mode facts, the measured
  plan-mode-plus-run-scope-lock hazard, and the install commands.
