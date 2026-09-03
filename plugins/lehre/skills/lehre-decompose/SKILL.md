---
name: lehre-decompose
description: "Use on a blank page, after lehre-preflight reports greenfield, to turn a stated project intent into build units, the seams between them, and an enforced build order. Trigger on 'start this project properly', 'initialize this repo', 'break this down into pieces and connect them', 'what should I build first', or 'lehre decompose'. Produces units whose order is denied at the tool-call layer, not a plan anyone can skip."
---

Turn "I want to build X" into units, seams, and an order that is **enforced**.
A dependency-ordered plan nobody is held to is the looseness this plugin exists
to remove.

## Steps

1. **Refuse to guess the intent.** If the user has not said what the project is
   for, ask once — what it does, who calls it, what it must not do. Do not
   invent a domain from the repository name. Record their answer verbatim; it
   becomes the `intent-derived` provenance for every rule `lehre-codify` writes
   next.

2. **Dispatch `spec-decomposer`, one concern per dispatch, in parallel.** Give
   each dispatch exactly one concern from the stated intent. Each returns
   candidate units with the paths they own and what they must not know about.
   Dispatching one agent over the whole intent produces a flat list with
   invented seams; the parallelism is what keeps the concerns independent.

3. **Derive the seams, not just the pieces.** For every pair of units that must
   interact, name the seam: what crosses it, in which direction, and which side
   owns the type. A unit list with no seams is a folder layout, not an
   architecture — and it is the seams that become `python-import` rules.

4. **Order by seam direction, then declare it.** A unit depends on every unit
   whose seam it consumes. Contracts before the things written against them;
   transport last, so it cannot shape the domain. Reject any ordering that needs
   a cycle — `lehre_core` refuses a cyclic graph at validation time anyway, and
   catching it here is cheaper than catching it at the first denial.

5. **Write the units into `.lehre/ruleset.json`.** If the file does not exist,
   create it with `"rules": []` — `lehre-codify` fills those in. Record the
   user's intent **verbatim** in the top-level `intent` field, and each unit's
   `owns` and `must_not_know` alongside its `paths` and `depends_on`. These are
   persisted rather than remembered because `lehre-validate` dispatches
   `spec-fidelity-auditor` against them in a later session, and a recollection
   of what the user asked for is not evidence. Then:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lehre_cli.py" validate
   ```

   If validation fails, fix the units; never leave an invalid ruleset on disk,
   because the hook fails closed and will deny every write until it parses.

6. **Show the user what is now enforced**, and say plainly that writing into a
   later unit will be **refused** until the earlier one passes `lehre-validate`.
   This is the moment to surface it, not the moment of the first denial.

## Output format

```
intent (verbatim, becomes rule provenance)
  "A CLI that ingests CSV exports from three vendors, normalises them to one
   schema, and writes Parquet. Must never mutate the input files."

units and seams
  1  contracts   src/contracts/*   depends on: —
       owns   the normalised row schema and the VendorAdapter protocol
       seam   -> adapters, domain   (types flow out; nothing flows in)
  2  adapters    src/adapters/*    depends on: contracts
       owns   one module per vendor, each implementing VendorAdapter
       seam   <- contracts (protocol)   -> domain (normalised rows only)
       must not know   the output format, or that Parquet exists
  3  domain      src/domain/*      depends on: contracts
       owns   normalisation, validation, the never-mutate-input invariant
       must not know   which vendor a row came from
  4  writer      src/writer/*      depends on: contracts
       owns   Parquet emission
  5  cli         src/cli/*         depends on: adapters, domain, writer
       owns   argument parsing, exit codes
       built last, so transport concerns cannot leak inward

enforced build order
  contracts -> (adapters | domain | writer) -> cli
  adapters, domain and writer are independent — they may be built in parallel.

now in force
  A write into src/cli/* is DENIED until adapters, domain and writer each pass
  lehre-validate. Escape hatch: LEHRE_DISABLE_GUARD=1.

next: lehre-codify — the units exist; the rules that govern them do not yet.
```

## Rules

- **Name what each unit must not know.** That sentence is what becomes an
  enforceable `python-import` rule. A unit description with no negative space
  produces no enforceable rule.
- **Independent units must be reported as independent.** Serialising units that
  have no seam between them invents a dependency and slows every later build for
  no reason.
- **Never mark a unit done here.** Only `lehre-validate` writes a done-marker.
- Units may be revised later, but revising a unit whose dependents are already
  validated invalidates them — say so before doing it.

## Resources

- `references/ruleset-schema.md` — the unit fields this skill writes (`id`, `paths`,
  `depends_on`, `owns`, `must_not_know`, `reason`) and the top-level `intent` field, plus
  why the done-marker belongs to `lehre-validate` alone. Read it before writing units.
