---
description: Prove an alignment pass changed nothing observable — test-suite equivalence, doc-vs-code re-sync, no stray drift
argument-hint: <area-dir> [dimension]
---

Verify that `/consistency-align` on `[dimension]` (or every aligned
dimension, if omitted) changed **only** what the Pattern Card said it
would — same behavior, same public surface, and docs that still describe
the code accurately.

This is an **equivalence check, not a security audit** — the closest
analogue in the original modernization pipeline is its hardening pass,
reused here for a different purpose: proving no behavioral drift, not
finding vulnerabilities.

## Step 1 — Test-suite equivalence

If `/consistency-preflight` Check 3 came back green: run the full test
suite (or the scoped subset covering the aligned modules) on the branch
from `/consistency-align`, and compare pass/fail counts and results
against the baseline recorded in `PREFLIGHT.md`. Any newly-failing test is
a **blocker** — either the alignment introduced a behavior change, or the
test itself asserted the old variant's shape and needs updating (distinct
outcomes; say which).

If Check 3 came back red (no runnable test suite): degrade to a
**structural diff review** — for every file `/consistency-align` touched,
confirm the diff is limited to the declared dimension (no incidental
logic change riding along) — and say plainly that this is not equivalence
proof, only diff-scope proof.

## Step 2 — Documentation re-sync

For every module aligned, check whether `README`/docstrings/comments that
described the *old* variant still do — a stale example, a comment
referencing the removed pattern, a doc snippet showing the pre-alignment
form. This is the same "docs vs. code" drift concern `/consistency-scan`
was built to avoid re-litigating for documented conventions — here it's
the mirror case: alignment can *create* drift by changing code without
touching the prose beside it.

## Step 3 — Workflow orchestration (preferred when available)

If the **Workflow tool** is available in this session:

```
Workflow({
  scriptPath: "${CLAUDE_PLUGIN_ROOT}/workflows/verify.js",
  args: { area: "$1", dimension: "<dimension>" }
})
```

This fans out one **equivalence-verifier** per aligned module, each
re-reading its diff against the Pattern Card's canonical form and the
module's tests, then an independent **consistency-critic** pass
adversarially re-checks every PASS verdict before it's trusted (the
signature false-negative here is a verifier that only re-runs the tests
the aligner already ran, missing a behavior change the existing test suite
never covered). Report `refuted` count — the precision the second pass
bought.

**Fallback** (no Workflow tool): run Steps 1–2 yourself per module.

## Write

`analysis/$1/VERIFICATION.md`:
- **Scorecard** — modules verified, pass/fail/blocked
- **Test results** — before/after counts, or "structural-diff-only" note
- **Doc-drift findings** — any stale doc/comment found, with the fix
- **Blockers** — anything that must be resolved before this phase is
  considered done, each tied back to the `ALIGN_NOTES.md` entry it
  concerns

## Present

If clean: tell the user this phase is verified and the branch is ready
for normal review/merge — this command never merges or pushes. If not
clean: list blockers and suggest fixing them in `/consistency-align`
before re-running this command, not merging around them.
