# What happens when these plugins share a session

Nothing in a plugin's own README says what happens when another plugin is installed
alongside it. This page collects what the guard hooks, the diff baselines, and the
ambient plugins actually do when they overlap, grounded in hook source rather than in
what a README implies. `delegation.md` covers the dispatch side; this page covers what
happens once those dispatches — or a direct edit — land while a guard is watching.

## Five hooks already arbitrate every edit

Five werkstoff plugins register a `PreToolUse` hook, and all five are inert until the
repository shows a specific piece of state — none of them polices an unrelated
project the moment it happens to be installed.

| plugin | matcher | script | inert unless | escape hatch |
|---|---|---|---|---|
| andon | `Write\|Edit` | `hooks/andon_enforce.py` | a ledger exists in the current working directory | `enforcement: off` in `.claude/andon.local.md` |
| confab | `Edit\|Write` | `scripts/hooks/guard_edit_scope.py` | a remediation-scope lock is open at `analysis/confab/remediation_scope.json` | delete the lock file, or run without `--fix` |
| confab | `Bash` | `scripts/hooks/guard_bash_scope.py` | `analysis/confab/` does not exist in the repo | run the command outside a confab-managed session, or remove `analysis/confab/` |
| cupertino | `Skill\|Task\|Agent\|Write\|Edit\|Bash` | `hooks/pretooluse_guard.py` | no `.cupertino/` state directory exists | `CUPERTINO_DISABLE_GUARD=1` |
| self-assess | `Write\|Edit\|MultiEdit` | `hooks/guard_target_edit.py` | no self-assess edit-scope lock is open at `analysis/self-assess/edit_scope.json` | named in the hook's own deny message |
| takt | `Skill\|Task\|Agent\|Write\|Edit\|MultiEdit` | `hooks/takt_guard.py` | no beat declaration exists at `.claude/takt.local.md` | `TAKT_DISABLE_GUARD=1` |

Two details matter beyond the table. First, andon's matcher covers `Write` and `Edit`
only — it does not list `MultiEdit`, unlike self-assess's matcher on the same three
tool names. Second, two matchers reach upstream of the edit itself by covering
`Skill|Task|Agent`, so they can intercept a dispatch and not only a file write.
cupertino uses that reach for its own ordering — refusing `cupertino-focus` or
`cupertino-longevity` before `cupertino-backwards` has run, via
`GATED_AFTER_BACKWARDS`. takt's matcher is the widest of the five, adding
`MultiEdit` on top of the same dispatch tools, and it gates declared beat order
across plugins rather than within one. The other three reach only the write tools.

## All five fail closed, with one shared exception

Every one of these five hooks fails closed: an unexpected internal error — a
malformed JSON payload, a filesystem error, anything the hook did not anticipate —
denies the tool call rather than silently allowing it, and the deny message always
names the escape hatch. andon's own docstring states the reasoning plainly: a hook
that fails open on its own bug is not an enforcement hook, and three of andon's own
guards were once observed failing silently that way before this rule was adopted.

self-assess's and confab's edit-scope guards carve out exactly one shared exception
to that rule: if the plugin's own shared `scripts/lib/` package is missing or broken
at import time, the hook degrades to a single stderr warning plus an allow, not a
deny. The reasoning both docstrings give, nearly word for word: a packaging defect in
the plugin itself is not evidence that the edit under review violates a rule, and
blocking every future edit in every repository because of a broken import is a
strictly worse failure than one missed enforcement check. andon's and cupertino's
guards carry no such carve-out in their source — their fail-closed behavior has no
documented exception.

## Why a hook cannot tell whose edit it is

self-assess's guard states the constraint every one of these hooks has to design
around, verbatim:

> PreToolUse's payload carries no field identifying which agent/plugin issued the
> Edit/Write/MultiEdit.

The consequence is concrete, not theoretical: self-assess's own guard once gated on
repo-level state — "does this repo look self-assess-managed" — and that swept every
edit in the whole session, from any plugin or a direct user edit, into the gate the
moment a repo merely had `analysis/self-assess/` on disk, blocking confab, cupertino,
and codebase-consistency remediators along with ordinary direct edits. The general
rule that follows: gate on a per-dispatch lock, never on repo-level state, whenever
the question a hook is answering is "did the currently-in-flight remediation issue
this specific edit." self-assess's `edit_scope.json` and confab's
`remediation_scope.json` both do exactly that now — opened immediately before a
remediator agent is dispatched, holding the specific file(s) that dispatch is allowed
to touch, and closed after.

That rule does not extend to every hook in the table. andon's and cupertino's guards
answer a different question — "is the ledger in a stop state" and "has the required
ordering step already run" — which is legitimately repo-level state rather than a
per-dispatch attribution problem. Only self-assess and confab's edit-scope guards are
solving the "whose edit is this" problem the quoted constraint describes, and only
those two need a per-dispatch lock rather than a durable flag.

## Two diff baselines

The official `security-guidance` plugin computes its own baseline independently of
whatever a controller session has computed for its own purposes. It runs `git stash
create` at `UserPromptSubmit` to capture a baseline SHA, then reviews the diff
against that baseline at the `Stop` hook — with no awareness of any `BASE_SHA` a
controller recorded via `git rev-parse HEAD` before dispatching an implementer (the
pattern `subagent-driven-development` uses for its own review packages). Two
uncoordinated baselines exist in the same session whenever both are active: one the
controller tracks for its task-review diffs, and one security-guidance tracks for its
own Stop-hook review.

The plugin documents its own escape hatch for exactly this overlap: setting
`ENABLE_STOP_REVIEW=0` disables only the Stop-hook diff review — commit and push
reviews stay active — and the plugin's own README names the intended case as
"multi-agent / shared-worktree setups where another agent can move HEAD between a
worker's turns." A session running subagent-driven-development's implementer/reviewer
cycle alongside security-guidance is exactly that case.

## Do not combine

`learning-output-style` instructs the model to stop at decision points and hand a
small, meaningful piece of code (5-10 lines) to the human rather than writing it
directly. That instruction is the direct opposite of `subagent-driven-development`'s
continuous-execution premise, which names only four conditions that should stop a
running plan — an irreversible or destructive operation, a security-sensitive action,
a side effect outside the worktree, or a plan broken enough that every path forward
is a guess — and explicitly rejects "should I continue?" prompts between tasks as a
waste of the human partner's time. Running both in the same session means one
instruction set pauses for contributions the other set was told never to pause for.

## Name collisions

`code-simplifier` ships as an agent twice: once in its own plugin, and once again
inside `pr-review-toolkit`. Both declare the same agent name (`code-simplifier`), the
same `model: opus`, and a byte-identical system-prompt body — the only difference is
the frontmatter `description` field's format (a short one-line description in the
standalone plugin, a longer description with worked examples in the
`pr-review-toolkit` copy). Installing both plugins yields two agent definitions
sharing one name; nothing in either plugin's manifest declares which one a bare
dispatch by that name resolves to.

A second, less certain collision: `code-modernization` and self-assess both write a
file named `MODERNIZATION_BRIEF.md` with different schemas — self-assess's transform
brief and code-modernization's own brief are not interchangeable documents that
happen to share a filename. self-assess writes to its own output directory (default
`analysis/self-assess/`, resolved through `self_assess_cli.py resolve-output-path`);
code-modernization's `modernize-brief` command writes to `analysis/$1/
MODERNIZATION_BRIEF.md`, where `$1` is a target name supplied to the command. The two
only collide if a session configures both to write into the same `analysis/`
subdirectory. This is presented as an unverified hazard rather than a confirmed
conflict: no collision guard exists in either plugin's write path, but no test or
run was found that actually forces the two into the same directory to prove the
collision happens.

## Ambient, not invoked

Several plugins in the official set are never dispatched the way an agent or skill
is — they run continuously in the background for the whole session instead of being
a participant a controller adds to a workstream:

- `security-guidance` installs `SessionStart`, `UserPromptSubmit`, `PostToolUse`, and
  `Stop` hooks that fire on every matching event for the life of the session, not on
  request.
- The two output-style plugins, `learning-output-style` and `explanatory-output-style`,
  inject their instructions once at `SessionStart` and then shape every response for
  the rest of the session — there is no per-task moment where either one is "used."
- The twelve LSP plugins (`clangd-lsp`, `csharp-lsp`, `gopls-lsp`, `jdtls-lsp`,
  `kotlin-lsp`, `lua-lsp`, `php-lsp`, `pyright-lsp`, `ruby-lsp`, `rust-analyzer-lsp`,
  `swift-lsp`, `typescript-lsp`) supply language-server diagnostics as a standing
  capability available to whatever agent happens to be running, rather than
  appearing as a workstream of their own. A reviewer dispatched into a repository
  with the matching LSP plugin installed sees sharper diagnostics as a precondition
  of the environment it runs in — the LSP plugin is not itself a gate a fix has to
  pass, and it is never a defender, challenger, or verifier a controller names in a
  dispatch.
