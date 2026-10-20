---
name: nacharbeit-fix
description: "Use to apply the haiku- and sonnet-tier backlog of a completed nacharbeit review: one remediator per file at the file's tier, a blind sonnet verifier that re-reads the file and runs the post-checks its kind needs (py_compile, node --check, the hook test, the viewer standard), one repair round on rejection, all under a PreToolUse hook that denies every edit outside the fix lock. Trigger on 'apply the nacharbeit findings', 'fix what the review found', 'rework these plugins to the standard', 'nacharbeit fix'. Requires a persisted, calibrated review in analysis/nacharbeit/; opus- and human-tier entries are listed for a person and never applied; never commits."
---

Rework the part to spec, then measure it again before it leaves the bench. Every edit
in this pass is authorized by a lock the guard hook reads, verified by a model that
did not make it, and checked by a script that does not care who did.

## Steps

1. **Preflight.** Run `nacharbeit-preflight`. It must show `run.json=present`, no open
   lock, and `own guard ... present, declared, denies`. A line reading `NOT LIVE` (an install
   synced without `hooks/`, or `NACHARBEIT_DISABLE_GUARD=1` set) means the pass would run
   unguarded: stop and say so; `build_fix_args.py` refuses on it too. Name every other live guard: a denial from takt, lehre, andon, zeugnis,
   befund or cupertino during this pass is reported as "blocked by <plugin>" and
   never retried with that plugin's escape hatch.

2. **Build the work items and open the lock:**

   ```bash
   python3 -B "${CLAUDE_PLUGIN_ROOT}/scripts/build_fix_args.py" [--write-roots plugins/ tools/]
   ```

   It refuses a review that is not completed and calibrated, and a lock that is already
   open. On success it has written `analysis/nacharbeit/fix_scope.json` (every file the
   review touched with its tier — see `references/fix-scope-schema.md`) and snapshotted each
   plugin about to change to `analysis/nacharbeit/pre-fix/`. It has **not** written
   `fix-run.js`: that comes only after step 3 shows the guard fires. From this moment the
   guard should deny any edit outside the lock, any edit to an opus- or human-tier file,
   and any git state change. Tell the user the file count by tier and the excluded list.

3. **Prove the guard fires** — as a separate command, so the hook sees it first:

   ```bash
   python3 -B "${CLAUDE_PLUGIN_ROOT}/scripts/build_fix_args.py" --confirm-guard
   ```

   The guard writes `guard-heartbeat.json` on every call while the lock is open; this
   bakes `fix-run.js` only if a heartbeat for *this* lock exists. Without one the hook is
   not registered in this session: the script deletes the lock, writes nothing, and exits
   1. Report that, name the likely cause (plugin installed without `hooks/`, plugin
   disabled, a session started before the hook was installed), and stop. Never launch a
   hand-made `fix-run.js`.

4. **Launch the pass** by the baked script path:

   ```
   Workflow({ scriptPath: "analysis/nacharbeit/fix-run.js" })
   ```

   Per file: a remediator at the file's tier applies the entries with Edit; a blind
   sonnet verifier re-reads the file, quote-checks the pre-fix evidence, runs the file's
   post-checks with Bash, and lists regressions; at most one sonnet repair round follows,
   driven only by the verifier's rejections.

   *Without the Workflow tool*: apply the entries of one file at a time yourself, in
   tier order, then dispatch `fix-verifier` for that file before touching the next.
   Never batch files into one dispatch.

5. **Check the whole pass and release the lock:**

   ```bash
   python3 -B "${CLAUDE_PLUGIN_ROOT}/scripts/post_fix_check.py" --release-lock
   ```

   It re-runs every post-check, diffs each touched plugin's contracts (output paths,
   settings files, env vars) against the pre-fix snapshot, and deletes the lock only when
   nothing failed and nothing moved. A kept lock is the result, not an obstacle: fix what
   it names, rerun, and only a person passes `--force`.

   A post-check that cannot run is skipped by name, not failed and not passed: outside
   werkstoff, a hook-script fix has no `hook-violation-<plugin>/` fixture for
   `verify_hooks_deny.py` to probe against, so that one check is listed under
   `postChecks.skipped` in `fix-check.json` and as `WARN post-check skipped` on stderr
   (the hook's unit test and `py_compile` still run). `clean: true` does not mean the skipped
   check passed. Report each one, and say the hook was never behaviourally probed.

6. **Report, hand off, stop.** List applied, skipped-with-reason, partially resolved and
   regressed files; list every opus- and human-tier entry verbatim; state that the
   changes are unverified beyond the post-checks and hand off to `andon:andon-verify` (or
   `andon-loop` for a ledger-recorded proof) and a human diff read. Do not commit.

## Output format

```
nacharbeit fix 2026-09-09T07:02:11Z (review 2026-09-09T06:12:04Z) — 41 files, 97 entries
  guard confirmed: seen firing on a Bash call at 2026-09-09T07:02:40Z for lock 2026-09-09T07:02:11Z
  resolved 33 · partially-resolved 4 · all-skipped 2 · regressions 1 · remediator-failed 0 · verifier-failed 1
  regressions
    plugins/lehre/hooks/lehre_guard.py — post-check failed: hook unit test (2 cases) → repair round did not clear it
  skipped with reason (7 entries)
    plugins/andon/skills/andon-loop/SKILL.md #2 — cross-file: the fix needs okf-ledger-schema.md to change first
  excluded (never applied)
    [opus ] plugins/zirkel/workflows/solve.js — design a real gate for each stage's output_contract
    [human] plugins/andon/skills/andon-loop/SKILL.md — decide whether scoped runs are supported at all
post-fix check: 38 post-checks passed, 1 failed, 1 skipped; contracts andon=clean, lehre=clean
  skipped plugins/lehre/hooks/lehre_guard.py — hook denies and stays inert: no hook-violation-lehre/ under /repo/test/plugins/fixtures
lock: KEPT (1 failed post-check) — fix plugins/lehre/hooks/lehre_guard.py, rerun post_fix_check.py --release-lock
UNVERIFIED beyond the post-checks. Next: andon-verify on the edited wires; read the diff before committing.
```

## Rules

- **One file per remediator dispatch.** A dispatch that touches five files cannot be
  reviewed as five decisions.
- **Never apply an opus- or human-tier entry**, however small the diff would be. The
  guard denies it; do not reach for `NACHARBEIT_DISABLE_GUARD=1`.
- **Never bypass another plugin's guard.** Report the denial and the file; stop that
  file.
- **Never commit, push, tag or reset during the pass.** The guard denies it; after the
  lock is released the diff is the user's to read and commit.
- **Never release the lock with `--force` on your own decision.**
- **Never launch a pass whose guard was not confirmed.** `--confirm-guard` failing is the
  result, not an obstacle; `NACHARBEIT_DISABLE_GUARD=1` makes the guard unconfirmable on purpose.

## Resources

- `scripts/build_fix_args.py` (twice: open the lock, then `--confirm-guard`), `scripts/post_fix_check.py` — run, in that order, around the workflow.
- `workflows/fix.js` — read to understand the remediate / verify / repair loop; its baked copy is what runs.
- `hooks/nacharbeit_guard.py` — the lock enforcement and the heartbeat; `hooks/test_nacharbeit_guard.py` proves it denies and allows.
- `references/fix-scope-schema.md` — read for the lock's fields and lifecycle.
- `agents/fix-verifier.md` — the fallback verifier for sessions without the Workflow tool.
