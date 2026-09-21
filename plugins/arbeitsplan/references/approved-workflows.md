# The four approved workflows

The single source for "where do I start". Four shapes cover the work this repository's
plugins actually do; each entry states what to install, what to say, what it writes, which
hook can deny it, and whether that has been measured. Nothing here is invented — a fact not
listed as measured is reasoned, and is labelled that way.

**A parser must not have to infer these facts from prose.** The six fields below are always
present, in this order, for every workflow: Mode, Install, Opening prompt, Writes to repo,
Hooks that may deny, Evidence.

**Contents** — [A. Build a feature](#a-build-a-feature) · [B. Understand an unfamiliar repo](#b-understand-an-unfamiliar-repo) · [C. Fix a bug, or harden a repo](#c-fix-a-bug-or-harden-a-repo) · [D. Design a UI, or review a plugin](#d-design-a-ui-or-review-a-plugin) · [permission-mode facts](#permission-mode-facts) · [measured hazard](#measured-hazard-plan-mode-plus-an-arbeitsplan-run-scope-lock) · [install commands](#install-commands)

---

## A. Build a feature

| | |
|---|---|
| **Mode** | `plan`, then approve with "Yes, and use auto mode" |
| **Install** | `zirkel@werkstoff` + `superpowers` + `pr-review-toolkit` |
| **Opening prompt** | Scope it before writing code, then build it, then gate the diff |
| **Writes to repo** | `.zirkel/runs/<run-id>/state.json` |
| **Hooks that may deny** | None of these three register one |
| **Evidence** | measured, 6 cells: the expected `zirkel-clarify-scope` never fired, on either model or mode -- [/examples/build-feature](/examples/build-feature) |

## B. Understand an unfamiliar repo

| | |
|---|---|
| **Mode** | `plan` throughout — it is read-only work |
| **Install** | `befund@werkstoff` (+ `zirkel@werkstoff`) |
| **Opening prompt** | Map the real module boundaries and what depends on what |
| **Writes to repo** | `analysis/befund/**` |
| **Hooks that may deny** | befund's guard is inert until `analysis/befund/edit_scope.json` exists |
| **Evidence** | measured, 4 cells: fired in 2 of 4, sonnet only -- [/examples/understand-repo](/examples/understand-repo) |

## C. Fix a bug, or harden a repo

| | |
|---|---|
| **Mode** | Manual or `acceptEdits`, NOT `plan` — the work is edits, and a ledger lock is involved |
| **Install** | `superpowers` + `andon@werkstoff` |
| **Opening prompt** | Find the root cause before changing anything, then prove the fix |
| **Writes to repo** | `analysis/andon/ledger/**` |
| **Hooks that may deny** | andon's PreToolUse denies every write outside the ledger while the ledger is in a stop state |
| **Evidence** | measured, 6 cells: 5 of 6, and the only workflow whose diffs actually landed -- [/examples/fix-bug](/examples/fix-bug) |

## D. Design a UI, or review a plugin

| | |
|---|---|
| **Mode** | `plan` until the brief is signed |
| **Install** | `cupertino@werkstoff` + `matrize@werkstoff` (UI) or `nacharbeit@werkstoff` (plugins) |
| **Opening prompt** | Work out what it should be before touching the markup / review this plugin against the standard |
| **Writes to repo** | `.cupertino/**`, `.design/**`, `analysis/nacharbeit/fix_scope.json` |
| **Hooks that may deny** | cupertino's guard arms on `.cupertino/`, matrize's on `.design/`, nacharbeit's while the fix lock exists |
| **Evidence** | measured, 8 cells: sonnet reached cupertino but fired `council`, not `backwards`; nacharbeit-lint fired 1 of 4 -- [/examples/design-ui](/examples/design-ui), [/examples/review-plugin](/examples/review-plugin) |

---

## Permission-mode facts

Stated for accuracy, not repeated per workflow above:

- Modes: `default` (shown as Manual; reads only), `acceptEdits` (reads, edits, common
  filesystem commands), `plan` (reads; edits blocked until you approve a plan), `auto`
  (everything, with a classifier reviewing actions), `dontAsk` (pre-approved tools only; CI),
  `bypassPermissions` (containers only).
- Approving a plan offers three choices: "Yes, and use auto mode" / "Yes, manually approve
  edits" / "No, keep planning".
- Shift+Tab cycles `auto -> default -> acceptEdits -> plan -> default`. `/plan` prefixes a
  single prompt without changing the session's mode.
- Auto mode needs a supported model (Opus 4.6+/Sonnet 4.6+/Fable) and an organisation that
  has not disabled it; `defaultMode: "auto"` does **not** take effect from project
  `.claude/settings.json` — only user or managed settings set it.
- A PreToolUse hook denial blocks in **every** mode, including `auto` and
  `bypassPermissions`, and inside subagents.

## Measured hazard: plan mode plus an arbeitsplan run-scope lock

Recorded in `test/workflows/evidence/plan-file-under-lock.md`, and re-derivable in under a
second with `bash test/workflows/reproduce_hazard.sh` — no tokens, no agents, no network. Two
denials, both `exit=2`:

- **The plan file.** While a run-scope lock is open, a write to `~/.claude/plans/<name>.md` is
  denied, because that path resolves outside the repository the run was compiled against. Plan
  mode permits only that one file, so a subagent under both a run-scope lock and plan mode has
  no legal move at all.
- **An in-scope path during a fan-out.** A write the lock's own `writeScope` names is denied
  too, while a `fanout-redundant` phase is in flight: every candidate writes inside its own
  worktree and exactly one diff is applied afterwards. That is what makes a merge conflict
  impossible here.

So do not pair workflow A's plan mode with an open arbeitsplan run. Neither denial is a
malfunction, and neither escape hatch (`ARBEITSPLAN_DISABLE_GUARD=1`, or removing the lock)
should be reached for to get past a guard doing its job — close the run, or plan outside it.

## Install commands

```
/plugin marketplace add Anselmoo/werkstoff
/plugin install <name>@werkstoff
```

`superpowers` and the official plugins come from the official marketplace instead, for
example:

```
/plugin install superpowers@claude-plugins-official
```
