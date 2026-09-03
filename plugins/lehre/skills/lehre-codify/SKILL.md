---
name: lehre-codify
description: "Use after lehre-preflight (brownfield) or lehre-decompose (greenfield) to research a code style, pattern and architecture doctrine from external authority plus real repository evidence, and write it to .lehre/ruleset.json as machine-checkable rules. Trigger on 'establish our code standards', 'what rules should this project follow', 'codify our architecture', 'research best practice for this stack', or 'lehre codify'. Every rule must cite an authority; a rule nobody can justify is refused."
---

Produce the doctrine. A rule reaches `.lehre/ruleset.json` only if it names an
external authority, carries an honest provenance label, and — if it is to be
`blocking` — a deterministic predicate.

Read `references/ruleset-schema.md` before writing anything.

## Steps

1. **Detect the stack and its versions** from the manifests actually present
   (`pyproject.toml`, `package.json`, `Cargo.toml`, `go.mod`). Judge idioms
   against the version the project *targets*, never the newest that exists.

2. **Dispatch `doctrine-researcher`, one rule-domain per dispatch, in parallel.**
   Domains: naming · module boundaries and layering · error handling ·
   dependency direction · test placement and shape · public API surface.
   Each returns candidate rules with a cited authority. Use `context7` for
   anything version-specific rather than answering from memory — this repo's
   CLAUDE.md requires it, and a rule derived from a stale recollection of a
   framework's conventions is worse than no rule.

3. **In brownfield only, dispatch `pattern-investigator` in parallel** to find
   what the repo already does, with `file:line`. A researched rule that
   contradicts settled, deliberate practice is a rule that will be waived on
   first contact — find that out now.

4. **Assign provenance honestly, per rule.**
   - `evidence-backed` — authority **and** real `file:line` here.
   - `intent-derived` — authority **and** a span quoted from the user's stated
     intent (recorded by `lehre-decompose`).
   - `scaffolded-default` — authority alone. **The normal case in greenfield.**

   Never cite `file:line` for a file that does not exist. On a blank page that
   is not a shortcut, it is a fabrication, and it is the specific failure the
   next step is dispatched to catch.

5. **Dispatch `rule-critic` over the whole candidate set.** It re-derives each
   `sourceMode` claim independently and hunts for forced consistency — a rule
   imposing uniformity where genuine variation was warranted. Drop or downgrade
   what it refutes. Do not argue with it on the strength of your own draft.

6. **Assign severity by what the predicate can actually decide.**
   `blocking` only where a deterministic check exists in the closed vocabulary
   *and* the violation is genuinely worth refusing a write over. Everything
   else is `advisory` — and where no machine predicate exists at all, use
   `check.kind: "judgement"` with an `asks` question rather than forcing a
   glob or AST query to stand in for judgement. A judgement rule is
   advisory-by-schema and reaches `violation-auditor` through `lehre-gauge`.

   A repo whose every rule is blocking gets bypassed with
   `LEHRE_DISABLE_GUARD=1` on day two, which enforces nothing at all.

7. **Write and validate.**

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lehre_cli.py" validate
   ```

   Show its output verbatim, including the gauge-tier note. If it fails, fix the
   ruleset before finishing — the hook fails closed on an unparseable file.

## Output format

```
stack: Python 3.11 (pyproject requires-python = ">=3.11"), ruff, pytest

rules written: 9   blocking 5 · advisory 4
  denied at write time  4     (1 blocking rule is linter-tier — sweep and CI only)

  id                      sev        provenance          authority
  no-api-to-db            blocking   intent-derived      Clean Architecture, Dependency Rule
  no-utils-dumping-ground blocking   scaffolded-default  Clean Code ch.2
  tests-live-in-tests     blocking   scaffolded-default  pytest good-practices
  no-bare-except          blocking   scaffolded-default  PEP 8
  ruff-clean              blocking   intent-derived      ruff (already the project's linter)  [gauge-tier]
  prefer-logging          advisory   scaffolded-default  Python logging HOWTO
  ...

rule-critic dropped 2 candidates
  no-inheritance          forced consistency — the codebase uses ABCs deliberately at
                          src/adapters/base.py:14; the rule would have banned a settled choice
  max-function-length     no deterministic predicate available in the closed vocabulary;
                          re-filed as advisory rather than left as an unenforceable "blocking"

next: lehre-gauge (brownfield — sweep what exists) or lehre-conform (greenfield — build unit 1)
```

## Rules

- **Every rule cites an authority.** No exceptions. `authority.source` is a
  required field and a rule without one is refused by the schema.
- **Never mark a rule `blocking` whose predicate is `linter`-kind and expect a
  write-time denial.** It is gauge-tier; the validator prints that split, and
  the ruleset should be written knowing it.
- **Prefer deferring to a tool the project already runs.** If ruff or eslint
  already encodes a rule, write a `linter` rule that runs it rather than a
  hand-rolled duplicate that will drift from the tool's own version.
- **Do not re-derive rules that already exist in `.lehre/ruleset.json`.** Amend
  it. Rewriting from scratch silently drops every waiver the project has agreed.

## Resources

- `references/ruleset-schema.md` — the full `.lehre/ruleset.json` schema: every field, the
  closed `check.kind` vocabulary, how `enforcement` is derived rather than declared, and a
  worked instance. Read it before writing or amending a rule.
