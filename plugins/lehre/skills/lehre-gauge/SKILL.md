---
name: lehre-gauge
description: "Use to sweep a codebase against the doctrine in .lehre/ruleset.json and report every violation with file:line, after lehre-codify has written rules. Trigger on 'check this code against our standards', 'where do we violate our own architecture', 'audit for antipatterns', 'gauge this repo', or 'lehre gauge'. Read-only — reports violations, never fixes them."
---

Measure the tree as it actually is. This skill changes nothing.

The gauge is a script, not a judgement: it runs the same evaluator the
PreToolUse hook uses, so a sweep and a denial cannot disagree about one rule.
Do not re-reason the rules in prose — that produces a second, drifting opinion,
which is the failure this plugin exists to remove reintroduced one level up.

## Steps

1. **Run the sweep.**

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lehre_cli.py" gauge --json
   ```

   Exit `0` clean · `1` the sweep did not come back clean · `2` ruleset
   unusable. Exit 2 means stop and fix the ruleset; it does **not** mean the
   code is clean. Exit 1 covers violations **and** files that could not be
   judged — a rule cannot be reported as holding over a file it never reached.

2. **Read `unevaluated_unparseable` as a separate category and report it
   separately.** A file that would not parse was not judged. Collapsing "could
   not be evaluated" into "clean" is how a sweep quietly under-reports, and the
   JSON keeps them apart precisely so the summary can too.

3. **Report any incomplete sweep.** If the script printed a directory-read
   warning to stderr, the file list is partial — say so in the summary rather
   than presenting a count as complete.

4. **Dispatch `violation-verifier` on a sample before presenting a large set.**
   For each distinct rule with hits, have one violation independently
   re-confirmed at its exact `file:line`. A rule whose sample is a false
   positive has a predicate that is too broad, and every hit it produced is
   suspect — say that instead of listing 200 findings.

5. **Dispatch `violation-auditor` for every entry in `needs_judgement_pass`, one
   rule per dispatch.** These are `judgement`-kind rules: no machine can decide
   them, so the script reports them rather than evaluating them. Pass the rule's
   `asks` question and its `matching_files`. Skipping this step is how a rule
   nobody checked becomes a rule counted as clean — the script deliberately
   refuses to fold them into the violation count so this cannot happen silently.

   If `needs_judgement_pass` is empty, say so; do not dispatch the auditor with
   nothing to audit.

6. **Group by rule, then by unit** — not by file. The actionable question is
   "which rule is this codebase failing", and a file-ordered list buries it.

7. **Stop.** Do not fix anything. `lehre-brief` orders the work;
   `lehre-conform` does it.

## Output format

```
swept 412 file(s) against 9 rule(s)          [complete]
27 violation(s): 22 blocking · 5 advisory    3 file(s) could not be evaluated

blocking
  no-api-to-db                    18 hits    unit: api
      src/api/orders.py:3         imports 'src.db.session'
      src/api/users.py:7          imports 'src.db.session'
      ... 16 more
      verified: src/api/orders.py:3 re-confirmed by violation-verifier
      why: an API handler reaching the session directly makes the transport
           layer un-testable without a database.

  no-utils-dumping-ground          1 hit     unit: —
      src/utils.py                path matches a forbidden pattern
      verified: re-confirmed

  ruff-clean                       3 hits    [gauge-tier — never denied at write time]
      src/adapters/vendor_b.py     F401 'os' imported but unused

advisory
  prefer-logging                   5 hits    unit: adapters

UNEVALUATED — not clean, not judged
  src/adapters/vendor_c.py   would not parse (rule no-bare-except)

next: lehre-brief — 22 blocking violations across 2 units need an order before anything is touched
```

## Rules

- **Never present a count from a run that errored.** A failed sweep leaves the
  previous output in place; confirm the numbers came from the run you think
  produced them.
- **`UNEVALUATED` is never folded into the pass count.** It is its own line.
- **Never fix anything here**, including a one-line obvious fix. A gauge that
  edits is a gauge nobody can trust to have measured the tree it reported on.
