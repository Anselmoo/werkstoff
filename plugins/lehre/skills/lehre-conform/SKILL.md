---
name: lehre-conform
description: "Use to build a greenfield unit, or to apply exactly one approved phase of LEHRE_BRIEF.md, with the doctrine's blocking rules enforced at the tool-call layer throughout. Trigger on 'build the next unit', 'implement phase 1', 'apply the approved fixes', 'make this conform', or 'lehre conform'. Refuses to act on an unapproved brief, and never marks its own work validated."
---

Do the work under the doctrine. The PreToolUse hook is active throughout — a
write that violates a blocking rule is refused, so conformance is not something
this skill has to remember.

## Steps

1. **Establish authorization.**
   - *Greenfield*: name the unit being built. Check it is buildable:

     ```bash
     python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lehre_cli.py" status
     ```

     A unit shown as `blocked` cannot be built — its dependency has not been
     validated. Say which, and stop.
   - *Brownfield*: read `LEHRE_BRIEF.md`. Proceed only if its header says the
     phase is approved. **One phase per run.** An unapproved brief is a stop,
     not a prompt to ask again.

2. **Pull only the rules that bear on this unit.** Filter `.lehre/ruleset.json`
   by the unit's paths and list them before writing anything. A doctrine dumped
   in full at the start of every unit is noise; the point is targeted retrieval.
   State any advisory rules too — those will not be denied, so they are the ones
   that need conscious attention.

3. **Write the code.** Expect denials, and treat one as information rather than
   an obstacle: a blocking rule fired because the design took a shape the
   doctrine forbids. Fix the design. Do **not** reach for
   `LEHRE_DISABLE_GUARD=1` — if a rule is genuinely wrong, amend it through
   `lehre-codify` so the change is recorded and reviewed, rather than bypassed
   silently for one write and left in force for everyone else.

4. **Dispatch `conformance-remediator` for mechanical findings only, one
   dispatch per (file, rule) cluster.** Never a batch spanning several files:
   a single dispatch that touches five files cannot be reviewed as five
   decisions, and one bad rewrite contaminates four good ones.

5. **Bring judgement findings to the user**, with the rule, the rationale, and
   the options. Do not implement a design decision the brief marked as needing a
   person.

6. **Stop without self-certifying.** Run the gauge to show the current state,
   then hand off:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lehre_cli.py" gauge --severity blocking
   ```

   **Never write a unit done-marker here.** Only `lehre-validate` does that.
   This skill's own report that the work looks correct is exactly the
   self-assessment the plugin exists to replace.

## Output format

```
unit: adapters          status: ready (contracts validated)
rules in force here: 6
  blocking   no-api-to-db · no-utils-dumping-ground · tests-live-in-tests · no-bare-except
  advisory   prefer-logging · docstring-on-public   <- not denied; watch these yourself

built
  src/adapters/base.py          VendorAdapter protocol, implements contracts.RowSchema
  src/adapters/vendor_a.py      CSV dialect + column map
  src/adapters/vendor_b.py      fixed-width parser

denials encountered (2) — each one changed the design, none were bypassed
  no-api-to-db    src/adapters/vendor_a.py tried to import src.db.session to look up a
                  vendor code. Resolved by passing the code map in from contracts,
                  which removed the adapter's database dependency entirely.
  no-bare-except  a bare except around the CSV sniffer -> except (csv.Error, UnicodeDecodeError)

remediator dispatches: 1  (tests-live-in-tests, src/adapters/test_vendor_a.py)

gauge, blocking only: 0 violations in src/adapters/*

NOT validated. This skill does not certify its own work.
next: lehre-validate adapters
```

## Rules

- **One approved phase per run**, brownfield. Two phases in one pass makes the
  approval gate decorative.
- **Never write `.lehre/units/<id>.done`.** That marker is `lehre-validate`'s
  alone, and the ordering gate is only meaningful because of it.
- **Never bypass the guard to finish faster.** A denial that gets
  `LEHRE_DISABLE_GUARD=1`'d is a rule that has silently stopped existing for
  everyone.
- **Never dispatch the remediator for a judgement finding**, however mechanical
  the resulting diff would look.
