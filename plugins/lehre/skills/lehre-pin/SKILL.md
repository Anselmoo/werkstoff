---
name: lehre-pin
description: "Use once a unit or phase is validated, to make its rules survive without the plugin: emit a CI check that runs the doctrine with no agent in the loop, and write behaviour tests around the code that was changed to conform. Trigger on 'make this stick', 'add CI for our standards', 'pin these rules', 'test the conformance changes', or 'lehre pin'. Two phases — the durable rule check, then the regression net."
---

Make the doctrine outlive the session. Every enforcement layer above this one
depends on an agent being in the loop; this one does not.

Two phases, both run:

## Phase 1 — pin the rules

1. **Emit a CI invocation of the real gauge**, not a reimplementation:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lehre_cli.py" gauge --severity blocking
   ```

   Exit `1` fails the job. A hand-written CI script that re-encodes the rules is
   a second implementation that will drift from the ruleset — the exact defect
   the shared evaluator exists to prevent.

2. **Prefer the project's own linter where the rule is expressible there.** A
   rule already covered by ruff/eslint/clippy belongs in that tool's config,
   where it runs on every developer's machine with no Python path and no plugin
   installed. Convert it and change the ruleset rule to `linter` kind pointing
   at the same tool. Reach for the gauge only for what a linter cannot say —
   layering, forbidden paths, unit ordering.

3. **Cover the write-time gap explicitly.** The PreToolUse hook does not see
   files written through `Bash`, and `linter`-kind rules are never write-time
   denials at all. CI is what closes both. Say so in the emitted config's
   comment, so the next reader knows why the job exists when a hook already does
   "the same thing".

## Phase 2 — pin the behaviour

4. **Write tests around what conformance changed**, not around the rule. The
   rule is already pinned by phase 1. What is unpinned is whether the
   conformance edit preserved behaviour — a layering fix that moved a database
   call behind a service is exactly the kind of change that compiles, passes
   every rule, and silently changes semantics.

5. **Target the seams the decomposition declared.** A test at a seam catches a
   later unit violating the contract long before a rule could; a test buried
   inside one unit's internals catches only that unit's refactors.

6. **Prove the test can fail.** State, per test, the mutation it would catch.
   A test written after the fact that passes against both the old and the new
   behaviour pins nothing, and this repo's `confab-assertion-audit` exists
   because that failure is common enough to need its own auditor.

## Output format

```
phase 1 — rules pinned

  .github/workflows/lehre.yml     runs lehre_cli.py gauge --severity blocking
                                  covers: Bash-written files, linter-tier rules,
                                  and any session with the plugin uninstalled
  pyproject.toml [tool.ruff]      + "TRY", "BLE"  <- absorbs no-bare-except and
                                  prefer-logging; ruleset rules converted to
                                  linter kind so there is one implementation, not two

  still gauge-only (no linter can express these)
    no-api-to-db             layering across packages
    tests-live-in-tests      file location
    unit build order         .lehre/units/*.done

phase 2 — behaviour pinned

  tests/adapters/test_vendor_a.py::test_code_map_passed_in_not_looked_up
      seam: contracts -> adapters
      would catch: reverting the fix, i.e. re-importing src.db.session to look
                   up the vendor code. Fails on the pre-conformance code.
  tests/contracts/test_schema_stability.py::test_row_schema_field_order
      seam: contracts -> everything
      would catch: a field reordered or renamed in RowSchema, which every
                   adapter and the writer silently depend on.

verified: both tests fail against the pre-conformance revision.
```

## Rules

- **Never reimplement a rule in CI.** Call the gauge. Two implementations of one
  rule is the drift the shared evaluator was built to eliminate.
- **Never claim a test pins behaviour without naming the mutation it catches.**
  If no mutation can be named, the test asserts nothing and should not be
  written.
- **Never pin an unvalidated unit.** Pinning cements the current behaviour; if
  `lehre-validate` has not passed, that behaviour is not known to be right.
