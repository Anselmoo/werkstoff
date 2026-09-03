---
name: lehre-brief
description: "Use after lehre-gauge to turn a violation set into an ordered remediation plan behind an explicit human approval gate, written to LEHRE_BRIEF.md. Trigger on 'plan the cleanup', 'what order should we fix these in', 'write the remediation brief', or 'lehre brief'. Refuses to run without a gauge result, and refuses to overwrite a brief written by another pipeline."
---

Order the work and stop for a human. Nothing downstream of this skill may run
until a person has approved the brief.

## Steps

1. **Refuse without inputs.** Requires `.lehre/ruleset.json` and a gauge result
   from this session. If either is missing, say so and stop — do not re-derive
   a violation set from memory or from a stale report. A brief built on
   remembered findings plans work against a tree that may no longer exist.

2. **Guard provenance before writing.** If `LEHRE_BRIEF.md` already exists, read
   its header. Proceed only if it carries `provenance: lehre`. If the header is
   absent or names another pipeline, **stop and report it** — this repository's
   `docs/orchestration/references/routing.md` records a real, unguarded clash
   where two plugins wrote one filename with different schemas and nothing
   noticed. Do not become the third.

3. **Order the work: dependency first, then smallest blast radius.** A rule
   violated in a unit that other units depend on is fixed before its dependents,
   because fixing the dependent first will be undone. Within a dependency tier,
   smallest blast radius first — bank the certain wins before the contested
   ones. This is deliberately *not* largest-first.

4. **Separate mechanical from judgement, per finding.** Mechanical means the
   fix is fully determined by the rule and the location — an import moved, a
   file relocated, a construct swapped. Everything else needs a person. Label
   each item; `lehre-conform` dispatches only the mechanical ones to an agent
   and brings the rest to the user.

5. **Name what each phase does NOT cover.** Bounded scope stated up front, not
   discovered when the phase ends.

6. **Write `LEHRE_BRIEF.md` with a `provenance: lehre` header**, then **stop at
   the approval gate.** State explicitly that no code changes until the user
   approves, and name the exact next command.

## Output format

`LEHRE_BRIEF.md` opens with:

```markdown
---
provenance: lehre
ruleset: .lehre/ruleset.json
gauge_run: 27 violations across 412 files
status: awaiting-approval
---
```

then, per phase:

```
phase 1 — contracts   (2 violations, blast radius: 2 files)
  fixes first because adapters, domain and writer all consume its types;
  fixing them first would be undone by this phase.

  mechanical (2)
    tests-live-in-tests   src/contracts/test_schema.py -> tests/contracts/test_schema.py
    no-bare-except        src/contracts/loader.py:41   except: -> except OSError:

  judgement (0)
  NOT covered: the schema's field naming — no rule governs it yet.

phase 2 — api   (18 violations, blast radius: 11 files)
  mechanical (0)
  judgement (18)
    no-api-to-db  every handler imports src.db.session directly. The fix is a
    service layer that does not exist yet; this is a design decision, not a
    rewrite of 18 import lines. Bring to the user before any edit.
  NOT covered: whether the service layer belongs in an existing unit or a new one.

APPROVAL GATE
  No file is modified until you approve this brief.
  Approve, then run lehre-conform for phase 1.
```

## Rules

- **Never edit source here.** The brief plans; `lehre-conform` acts.
- **Never mark a phase mechanical to make it dispatchable.** An 18-file layering
  fix that needs a new service layer is judgement, however uniform the diff
  would look.
- **Never write a brief without the provenance header** — it is what the next
  run's guard reads.
- If the user approves only part of the brief, record which phases are approved
  in the header. `lehre-conform` applies exactly one approved phase per run.
