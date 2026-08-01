---
description: Apply the approved canonical form to every divergent site, in dependency-aware batches, in place
argument-hint: <area-dir> [dimension]
---

Execute one phase of `analysis/$1/CONSISTENCY_BRIEF.md` — align every
divergent site for `[dimension]` (or the brief's next unstarted phase, if
omitted) onto its approved canonical form. **Requires an approved brief**;
stop and say so if `CONSISTENCY_BRIEF.md` has no filled Approval Block, or
if the requested dimension's phase entry criteria aren't met.

Unlike a legacy-modernization transform, this is **in-place, not a parallel
tree**: there is no `legacy/` vs `modernized/` split, because there is no
old system running alongside a new one — there's one live codebase that
gets more consistent commit by commit. Work on a branch:

```bash
git switch -c consistency/$1-<dimension>
```

Never touch anything `/consistency-preflight` Check 6 or Check 0 flagged as
out of scope or off-limits, even if it diverges on this dimension.

## Step 1 — Pilot (in-session, one module)

Per the brief's Phase 1 instruction: align **one representative module**
yourself, directly — no fan-out yet. Read the module's current variant and
the canonical form from `CANON.json`, make the minimal edit that converts
it, run the module's own tests, and write `analysis/$1/PLAYBOOK.md`: the
exact edit pattern, every snag hit and how it was resolved (an import that
had to move, a signature that needed an adapter, a test fixture that
assumed the old shape), and the precise command that proves a module is
done. **This playbook is what every later batch follows — do not skip the
pilot even under time pressure; a wrong assumption caught here costs one
module, not the whole area.**

## Step 2 — Batched fan-out (remaining modules)

**Preferred — Workflow orchestration.** If the **Workflow tool** is
available in this session (this invocation is your authorization):

```
Workflow({
  scriptPath: "${CLAUDE_PLUGIN_ROOT}/workflows/align.js",
  args: {
    area: "$1",
    dimension: "<dimension>",
    units: [ { name: "<module>", path: "<repo-relative path>", deps: ["<sibling module names this one's canonical form depends on>"] } ]
  }
})
```

Enumerate the remaining divergent modules from `CANON.json`'s
`divergentSites` first (the workflow script has no filesystem access).
`deps` matters here more than it does in a version uplift: if module B's
canonical form calls into a shared type or utility that module A's
alignment introduces, B must not be batched until A has landed — get this
wrong and the fan-out either fails B for a reason that has nothing to do
with the playbook, or worse, B "succeeds" against a stale shared shape.

This runs **dependency-aware escalating batches** (small first, growing
once the playbook proves stable) **behind a per-batch circuit breaker**: if
a batch's build/test-pass rate drops below 2/3, the fan-out stops rather
than burning through the rest of the area on a playbook that's stopped
working. Report the agent count before launching. Fold any
`playbookGaps` the return value carries into `PLAYBOOK.md` before
re-invoking with `remainingUnits`/`failedUnits`/`blockedUnits`.

**Fallback** (no Workflow tool): align the remaining modules yourself,
one at a time, following the same playbook; run each module's tests before
moving to the next.

## What "align" never does

- **Never a rewrite.** The smallest edit that converts the divergent site
  to the canonical form. "While we're here" cleanups are a defect here,
  exactly as in a version uplift — they turn a reviewable consistency pass
  into an unreviewable one.
- **Never touches a `needs-human-decision` dimension.** If `CANON.json`
  marks the requested dimension that way, refuse and point at the brief's
  open question.
- **Never edits outside its declared module/dimension scope**, even to fix
  something adjacent and obviously wrong — report it as a new finding for
  a future `/consistency-scan`, don't fold it in silently.

## Write

`analysis/$1/ALIGN_NOTES.md`: per module, before/after example, tests run
and result, and any playbook gap it surfaced. This is the input
`/consistency-verify` reads to know what to check.

## Present

Report modules aligned / failed / blocked / not-yet-attempted, and the
single next command: `/consistency-verify $1` once a phase is fully
aligned, or the re-invocation command if the fan-out stopped early.
