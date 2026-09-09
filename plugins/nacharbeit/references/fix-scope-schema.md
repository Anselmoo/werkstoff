# The fix lock: `<state-dir>/fix_scope.json`

The per-dispatch lock a nacharbeit fix pass holds while it edits other plugins' files.
`hooks/nacharbeit_guard.py` reads it on every `Write`, `Edit`, `MultiEdit` and `Bash`
call and is inert when it does not exist. It answers the one question a PreToolUse
payload cannot: is this edit one the in-flight pass was given? (see
`docs/orchestration/references/hazards.md`, "Why a hook cannot tell whose edit it is").

## Shape

```json
{
  "runStamp": "2026-09-09T05:12:52Z",
  "createdAt": "2026-09-09T05:12:52Z",
  "reviewRunStamp": "2026-09-08T17:57:42Z",
  "stateDir": "analysis/nacharbeit",
  "writeRoots": ["plugins/", "tools/"],
  "files": {
    "plugins/andon/skills/andon-loop/SKILL.md": "sonnet",
    "plugins/andon/references/okf-ledger-schema.md": "haiku",
    "plugins/compass/workflows/solve.js": "opus",
    "plugins/andon/skills/andon-preflight/SKILL.md": "human"
  }
}
```

| field | meaning |
|---|---|
| `runStamp` | the fix run this lock belongs to (also the `fix-args.json` stamp) |
| `createdAt` | UTC time the lock was opened; `nacharbeit-status` calls a lock older than six hours stale |
| `reviewRunStamp` | the review run whose findings the pass applies |
| `stateDir` | where the pass keeps its state; writes under it are always allowed (the session must save the workflow's return value) |
| `writeRoots` | path prefixes the pass may write under; the workflow refuses any item outside them |
| `files` | every file the review touched, repo-relative, with its highest fix tier. `haiku` and `sonnet` entries may be edited; `opus` and `human` entries are listed deliberately so a denial can say "opus-tier, never auto-applied" instead of "unknown file" |

## Lifecycle

| moment | actor | effect |
|---|---|---|
| open | `scripts/build_fix_args.py` | writes the lock, snapshots each touched plugin to `<state-dir>/pre-fix/<plugin>/`, bakes `fix-run.js`; refuses when a lock is already open |
| held | `hooks/nacharbeit_guard.py` | denies edits outside `files`, edits to `opus`/`human` entries, edits with no determinable target, and git state changes |
| release | `scripts/post_fix_check.py --release-lock` | deletes the lock only when every post-check passed and `contract_diff` found nothing lost or moved; `--force` overrides with a stated reason |
| stale | `nacharbeit-status` | reports a lock older than six hours with the release command; the guard itself never expires a lock — a stale lock denies, which is the safe direction |

## What the lock is not

- Not a pattern list: matching is exact path equality after normalisation, never a glob.
- Not repo-level state: it exists only between `build_fix_args.py` and `post_fix_check.py`.
- Not a substitute for the other guards: takt, lehre, andon, confab, self-assess and
  cupertino keep arbitrating the same edits by their own markers, and a denial from one
  of them during a pass is reported as "blocked by that plugin", never bypassed.
