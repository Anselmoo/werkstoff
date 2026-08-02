---
name: self-assess-idiom-fix
description: This skill should be used when the user explicitly asks to "apply the modernization findings", "fix the idiom findings", or "auto-fix what code-idiom found". Applies only eligible modernization-category findings from code_idiom_summary.json, gated behind idiom_fix.mode="fix", one remediator dispatch per (file, kind) cluster, then hands off to andon-verify without self-verifying.
---

# self-assess-idiom-fix

Apply single-location modernization idiom rewrites that `self-assess-code-idiom` already found
and verified. Never touches `smell`-category findings -- those require design judgment this
skill explicitly refuses to attempt on its own.

## Step 1: The mode gate -- refuse outright in 'propose' mode

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/self_assess_cli.py idiom-fix-mode-gate --repo <repo_root>
```

A non-zero exit means `idiom_fix.mode` is not `"fix"` in `.claude/self-assess.local.md` --
stop and tell the user plainly that applying findings requires setting `idiom_fix.mode: 'fix'`.

## Step 2: Filter to eligible findings only

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/self_assess_cli.py filter-idiom-findings --findings <code_idiom_summary.json's findings list>
```

`eligible` contains only `category: "modernization"` findings with no `severityNote`.
`skipped` lists every finding excluded and why (`category!=modernization` or `severityNote
present`) -- report this list to the user rather than silently ignoring it.

## Step 3: Dirty-tree gate

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/self_assess_cli.py dirty-tree-gate --repo <repo_root>
```

Same behavior as `self-assess-transform-execute`'s Step 4: a dirty tree without an explicit
`require_clean_tree: false` and user confirmation halts here.

## Step 4: Cluster, open the edit-scope lock, then dispatch one remediator per cluster

Group `eligible` findings by `(file, kind)`. Before dispatching any remediator, open the
edit-scope lock naming every cluster's file up front -- `guard_target_edit.py`'s PreToolUse
hook is inert until this lock exists, and only authorizes edits to the files it names:

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/self_assess_cli.py open-edit-scope --repo <repo_root> \
    --mode idiom_fix --files <cluster 1's file> <cluster 2's file> ...
```

Then dispatch one `idiom-remediator` agent per cluster (safe to do in parallel -- the lock
names every cluster's file up front, so concurrent dispatches never race on it), handing each
only that cluster's findings -- never a batch spanning multiple files or multiple kinds in one
dispatch, and never a location not cited in the findings it was given.

Once every remediator has finished, close the lock:

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/self_assess_cli.py close-edit-scope --repo <repo_root>
```

## Step 5: Hand off to verification -- never self-verify

Rule `verify-dispatch-handoff`: after the remediators finish, tell the user explicitly this
change is unverified and hand off to `andon:andon-verify` (or `andon:andon-loop` for an OKF
ledger). Do not run any self-check of correctness in this skill.

## Never commit or push

This skill has no code path that invokes `git commit` or `git push`.
