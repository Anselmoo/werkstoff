# `.lehre/ruleset.json` — the schema

One file holds the whole doctrine: the rules, and (in greenfield) the units the
project is being built in. It is validated by `scripts/lehre_core.py`, which is
also what the PreToolUse hook and `lehre_cli.py gauge` evaluate — so a sweep and
a denial can never disagree about what a rule means.

Validate any edit to it with:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lehre_cli.py" validate
```

## Worked instance

```json
{
  "version": 1,
  "provenance": "lehre",
  "mode": "greenfield",
  "intent": "A CLI that ingests CSV exports from three vendors, normalises them to one schema, and writes Parquet. Must never mutate the input files.",
  "units": [
    {
      "id": "contracts",
      "paths": ["src/contracts/*"],
      "depends_on": [],
      "owns": "the normalised row schema and the VendorAdapter protocol",
      "must_not_know": ["any vendor's name, dialect or quirks", "the output format"],
      "reason": "Every seam is settled before anything is written against it."
    },
    {
      "id": "domain",
      "paths": ["src/domain/*"],
      "depends_on": ["contracts"],
      "owns": "normalisation, validation, the never-mutate-input invariant",
      "must_not_know": ["which vendor a row came from"],
      "reason": "Domain logic is written against a settled contract, never ahead of one."
    },
    {
      "id": "api",
      "paths": ["src/api/*"],
      "depends_on": ["domain"],
      "reason": "The transport layer is the last thing built, so it cannot shape the domain."
    }
  ],
  "rules": [
    {
      "id": "no-api-to-db",
      "title": "The API layer must not import the database session",
      "severity": "blocking",
      "sourceMode": "scaffolded-default",
      "authority": {
        "source": "Clean Architecture (Martin), the Dependency Rule",
        "citation": "Source code dependencies must point only inward, toward higher-level policy."
      },
      "evidence": [],
      "rationale": "An API handler reaching the session directly makes the transport layer un-testable without a database and lets request shape leak into persistence.",
      "antipattern": "from src.db.session import get_session inside a request handler",
      "check": {
        "kind": "python-import",
        "paths": ["src/api/*"],
        "forbid": ["src.db.*"],
        "allow": []
      }
    },
    {
      "id": "no-utils-dumping-ground",
      "title": "No module or package named `utils`",
      "severity": "blocking",
      "sourceMode": "scaffolded-default",
      "authority": { "source": "Clean Code (Martin), ch.2 Meaningful Names" },
      "evidence": [],
      "rationale": "A `utils` module has no owner and no cohesion; it accretes whatever had no home, and nothing is ever removed from it.",
      "antipattern": "src/utils.py holding a date formatter, an HTTP retry, and a regex",
      "check": { "kind": "forbid-path", "paths": ["utils.py", "utils/*", "helpers.py"] }
    },
    {
      "id": "ruff-clean",
      "title": "The declared linter must pass",
      "severity": "blocking",
      "sourceMode": "intent-derived",
      "authority": { "source": "ruff, the project's declared linter" },
      "evidence": [],
      "rationale": "The project chose this linter; a rule it already encodes should not be re-litigated here.",
      "check": { "kind": "linter", "paths": ["*.py"], "command": ["ruff", "check"] }
    }
  ]
}
```

## Fields

| field | required | meaning |
|---|---|---|
| `version` | yes | must be `1` |
| `provenance` | yes | must be `"lehre"`. A ruleset written by another pipeline is refused, not read |
| `mode` | yes | `greenfield` (blank page) or `brownfield` (existing tree) |
| `intent` | no | the **verbatim** project intent, recorded by `lehre-decompose`. Optional, but `spec-fidelity-auditor` cannot run without it — and a fidelity check is the only thing here that catches a unit which satisfies every rule and still is not what it was for. Stored rather than remembered: a session's recollection of what the user asked for is not evidence |
| `units` | yes (may be `[]`) | build units and their dependency edges |
| `rules` | yes | the doctrine |

### A rule

| field | required | meaning |
|---|---|---|
| `id` | yes | unique, kebab-case |
| `title` | no | one line, human-facing |
| `severity` | yes | `blocking` or `advisory` |
| `sourceMode` | yes | `evidence-backed` · `intent-derived` · `scaffolded-default` |
| `authority.source` | yes | the external doctrine this rests on |
| `authority.citation` | no | the specific line, quoted |
| `evidence` | required iff `evidence-backed` | `[{"file": ..., "line": ...}]` in **this** repo |
| `rationale` | yes | why the rule exists. Quoted verbatim in the denial message |
| `antipattern` | no | the concrete shape being prevented |
| `check` | yes | the predicate — see below |
| `enforcement` | **never written by hand** | derived from `check.kind`; any value in the file is overwritten |

### `sourceMode` — and why it is policed

- **`evidence-backed`** — external authority **and** real `file:line` in this repo. Only reachable in brownfield.
- **`intent-derived`** — external authority **and** a span quoted from the user's own stated project requirements.
- **`scaffolded-default`** — external authority alone, honestly labelled. **This is the normal case in greenfield**, not a degraded one.

`evidence-backed` with an empty `evidence` list is a schema error. A rule citing
`file:line` in a repo where no such file exists is the specific fabrication
`rule-critic` is dispatched to catch: a researcher under pressure to satisfy the
schema will invent a plausible citation before it will downgrade its own claim.

## `check.kind` — the closed vocabulary

Five kinds. An unknown kind is a **schema error**, never a skipped rule.

| kind | tier | fields | decides |
|---|---|---|---|
| `forbid-path` | hook | `paths` | writing a file matching `paths` at all |
| `require-location` | hook | `paths`, `allowed` | a file matching `paths` must also match `allowed` |
| `python-import` | hook | `paths`, `forbid`, `allow?` | layering — which modules a file may import |
| `python-construct` | hook | `paths`, `forbid` | named AST constructs (below) |
| `linter` | **gauge** | `paths`, `command` (argv list) | the linter's exit code |
| `judgement` | **judgement** | `paths`, `asks` | nothing — no machine decides it |

### `judgement` — the honest home for a rule no machine can decide

`doctrine-researcher` is instructed to return candidates whose predicate is NONE
("is this a process boundary", "does this handler own business logic"), and
`lehre-codify` files those as advisory. Before this kind existed the schema then
**refused to persist them**, because `check.kind` had to be one of the five machine
kinds — so the pipeline researched a rule class it could not store, and
`violation-auditor`, whose whole job is auditing exactly that class, was dispatched
by nothing because nothing could ever be in its input set.

A `judgement` rule closes that. It is:

- **advisory by schema.** `severity: blocking` with `kind: judgement` is a *validation
  error*, not a footnote — a blocking rule nothing can evaluate would deny nothing
  while appearing to, which is the failure the tier system exists to prevent.
- **required to carry `asks`** — the single question an auditor answers by reading.
  Without it there is nothing to dispatch on, so its absence is an error too.
- **never evaluated.** `evaluate_file` raises on it rather than returning "clean";
  `lehre_cli.py gauge` collects it into `needs_judgement_pass` and reports it, and
  `lehre-gauge` step 5 dispatches `violation-auditor` once per entry. It never counts
  toward the violation total and never fails a sweep on its own.

```json
{
  "id": "handler-owns-no-business-logic",
  "severity": "advisory",
  "sourceMode": "scaffolded-default",
  "authority": { "source": "Clean Architecture (Martin), policy vs transport" },
  "rationale": "A pricing rule computed in a handler is the only place that rule lives.",
  "check": {
    "kind": "judgement",
    "paths": ["src/api/*"],
    "asks": "Does this handler compute a value the domain should own?"
  }
}
```

**Tier is derived, not declared.** Four kinds are decidable inside a
`type: "command"` PreToolUse hook. `linter` is not — the content being written
is not on disk yet, and shelling a linter out to a temp tree inside a 15-second
hook is neither fast nor trustworthy. So a `blocking` + `linter` rule fails a
sweep and fails CI but does **not** deny a write, and `lehre_cli.py validate`
prints that split explicitly. A rule everyone believes blocks and doesn't is
worse than one honestly labelled.

### Named constructs for `python-construct`

`bare-except` · `broad-except` · `wildcard-import` · `mutable-default-arg` ·
`global-statement` · `print-call` · `assert-statement`

Closed on purpose. "Forbid an arbitrary node shape" is where a deterministic
check quietly becomes a half-implemented linter — reach for `linter` instead.

### Matching rules

- Path patterns are **fnmatch, never regex**, tested against the full
  repo-relative path *and* the bare basename, so both `*.py` and `src/api/*`
  behave as an author expects.
- Module patterns are dotted globs; `src.domain.*` matches the package `src.domain`
  itself as well as its children.
- `from a.b import c` is checked against both `a.b` and `a.b.c`, but reports
  **one** violation per import statement.

Regex is absent by design. Three of the six silent defects in this repo's
CLAUDE.md are regex forms that match nothing and raise nothing — `[^.]{0,80}`
cannot span a dotted filename, `[^\n]` in a bracket expression means "not
backslash, not the letter n", `\b!==\b` never matches. A glob cannot express
any of them.

## Units and build order

A unit is a slice of the tree with a dependency edge. Writing into a unit is
**denied** while any unit it depends on is unvalidated.

### Unit fields

| field | required | meaning |
|---|---|---|
| `id` | yes | unique, kebab-case |
| `paths` | yes | globs this unit owns |
| `depends_on` | no | unit ids that must be **validated** before this unit may be written |
| `owns` | no | one line: what this unit is responsible for |
| `must_not_know` | no | the negative space — what this unit must never reference. This is what becomes an enforceable `python-import` rule, and what `spec-fidelity-auditor` checks by reading imports rather than trusting that a layering rule was written for every seam |
| `reason` | no | quoted in the denial message when the order gate fires |

The done-marker `.lehre/units/<id>.done` is written by `lehre-validate` alone —
never by `lehre-conform`, and never by hand in normal use. A unit is not done
because someone wrote its files; it is done because its rules and its seam were
checked. A cycle in the graph is rejected at codify time, since no build order
could ever satisfy it.
