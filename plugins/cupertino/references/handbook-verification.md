# Fix verification protocol

`cupertino-handbook-fix` is the plugin's only Edit-capable skill. This
document is the single source of truth for its safety discipline —
`cupertino-handbook-fix/SKILL.md`, `agents/handbook-remediator.md`, and
`agents/handbook-verifier.md` all point here rather than each repeating
it.

## The opt-in gate

`cupertino-handbook-fix` refuses to run past reporting eligible findings
unless `.claude/cupertino.local.md`'s `handbook.fix.mode` is explicitly
set to `fix` (default `propose`). This holds with zero exceptions,
including a direct request to "just do it anyway" — redirect the user to
the settings file instead. `cupertino-handbook-check` itself is
unaffected by this gate; it's fully available in `propose` mode, since
it's read-only.

## The dirty-tree guard

Before touching anything, `cupertino-handbook-fix` runs `git status
--porcelain`. If the tree isn't clean, it tells the user plainly that this
step is about to edit tracked files and asks them to commit or stash
first, or explicitly confirm proceeding anyway — never proceed silently on
a dirty tree.

## One remediator dispatch per finding

`handbook-remediator` is dispatched once per eligible (`mechanical: true`)
finding from `cupertino-handbook-check`'s sidecar, each dispatch carrying
only that one finding's `evidence`, `title`, and `suggestedFix` — never a
batch covering multiple findings. A `blocked` return is reported verbatim
and the loop moves to the next finding; it is never retried with a
broader prompt or a second-guessed fix.

## The blind adversarial pair — the load-bearing mechanic

`self-assess-idiom-fix` hands every fix off to `andon-verify`'s external
tribunal (Defender/Challenger/Verifier, run by a different plugin).
`cupertino` cannot depend on `andon` being installed, so it internalizes
the same discipline as a **self-contained pair**: immediately after
`handbook-remediator` applies a fix — before moving to the next finding —
`cupertino-handbook-fix` dispatches `handbook-verifier`, a fresh agent
with no memory of the fix that was just applied.

`handbook-verifier`'s dispatch prompt contains **only**:

1. The handbook rule text and its `detectionSignal` (from the handbook
   artifact, via the original `cupertino-handbook-check` finding).
2. The **original, pre-fix** violation evidence from
   `handbook-drift-auditor`'s finding — the `evidence`/`title` fields
   `cupertino-handbook-check` wrote to the sidecar, not anything
   `handbook-remediator` said about its own change.
3. An instruction to freshly `Read` the file's current state itself.

It **never** receives `handbook-remediator`'s own output: not its
description of what it changed, not its stated confidence, not its
reasoning. This is deliberate and is the one detail that could silently
regress if a future edit "helpfully" passes the remediator's summary
along — a verifier that sees the fixer's narrative can be talked into
agreement by it, which defeats the entire point of an independent check.
Both `handbook-remediator.md` and `handbook-verifier.md`, and
`cupertino-handbook-fix/SKILL.md`'s own Step 4, state this constraint
explicitly rather than relying on this document alone.

`handbook-verifier` reports `{compliant: bool, reasoning, evidence}` — no
persona framing, a plain independent judgment. A `compliant: false`
verdict is reported as a failed fix, never silently retried or
self-overridden by `cupertino-handbook-fix`.

## No commits, ever

Neither `cupertino-handbook-fix` nor either agent it dispatches commits or
pushes, at any point. That stays a manual, human decision.
