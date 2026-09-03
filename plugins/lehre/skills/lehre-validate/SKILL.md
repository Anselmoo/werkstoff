---
name: lehre-validate
description: "Use after lehre-conform to independently check that a unit satisfies its rules AND actually does what the project intent said it would, then close it so dependent units become buildable. Trigger on 'validate this unit', 'is this actually done', 'check the work before moving on', or 'lehre validate'. The ONLY skill that writes a unit done-marker — nothing else may certify a unit complete."
---

Decide whether a unit is genuinely finished. This is the gate the whole build
order rests on: a dependent unit becomes writable only when this skill closes
its dependency, so closing one carelessly disables the ordering guarantee for
everything downstream.

## Steps

1. **Never validate work you just did in the same reasoning pass.** Dispatch the
   checks. `lehre-conform`'s own account of its work is the input under review,
   not evidence — a self-graded pass is what this skill exists to replace.

2. **Run the deterministic gauge over the unit's paths.**

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lehre_cli.py" gauge --severity blocking
   ```

   Any blocking violation inside the unit is an immediate fail. Report it and
   stop; do not fix it here.

3. **Dispatch `violation-verifier` on anything the gauge could not evaluate.**
   `UNEVALUATED` is not a pass. A file that would not parse was not judged, and
   closing a unit on an unjudged file is exactly the "looks correct, silently
   does nothing" shape this repository catalogues.

4. **Dispatch `spec-fidelity-auditor` against the recorded intent.** Read
   `intent` and this unit's `owns` / `must_not_know` from `.lehre/ruleset.json`
   — never from your memory of the conversation. Rules passing is not the same
   as the unit doing what it was for. The auditor answers one question: does
   this unit deliver what the intent said, and does it respect what the
   decomposition said it must not know? A unit can be perfectly rule-compliant
   and still be the wrong unit.

   If the ruleset carries no `intent`, say so and **do not close the unit on
   rules alone** — report that fidelity is unchecked and ask for the intent, or
   have the user close it deliberately. Silently treating "not checked" as
   "passed" is the failure this whole step exists to prevent.

5. **Check the seams the decomposition declared.** For each seam this unit
   participates in, confirm the direction still holds — types flow the way the
   decomposition said, and the unit imports nothing from a unit it was declared
   not to know about. A layering rule may not exist for every seam; check the
   declared ones regardless.

6. **Close the unit only on a clean result.**

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lehre_cli.py" close <unit-id>
   ```

   On any fail — blocking violation, unevaluated file, fidelity gap, broken seam
   — do **not** close. Report what failed and name the skill that fixes it.

## Output format

```
unit: adapters

blocking rules       PASS   0 violations across 4 files
unevaluated          PASS   0 files failed to parse
seam direction       PASS   imports contracts only; no import of domain, writer or cli
spec fidelity        FAIL   spec-fidelity-auditor

  intent said: "ingests CSV exports from three vendors"
  found:       two adapters (vendor_a, vendor_b). vendor_c has no adapter and no
               stub; nothing in the unit reports its absence at runtime.
  this is not a rule violation — every rule passes. It is the unit not being
  what it was for, which no rule in the doctrine can express.

UNIT NOT CLOSED
  src/domain/* and src/cli/* remain DENIED at write time until adapters closes.
next: lehre-conform adapters — add the vendor_c adapter, then re-validate.
```

## Rules

- **Close on a clean result only.** A unit closed with a known gap silently
  unblocks every dependent, and the guarantee the build order provides is gone
  for the rest of the project.
- **Never close a unit because the user asked you to.** If they want the gate
  lifted, that is `LEHRE_DISABLE_GUARD=1` — visible, temporary, and theirs.
  A done-marker written to satisfy a request is a permanent false record.
- **Report fidelity failures as distinct from rule failures.** They need
  different fixes, and merging them hides the one no rule can catch.
- **Never fix anything here.** Validation that edits is validation nobody can
  trust to have measured the thing it graded.
