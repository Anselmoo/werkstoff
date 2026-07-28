# confab

Audits AI-generated code quality across four independent domains —
hallucinated dependencies, weak test assertions, contract drift, and
agentic-loop reliability — with independent verification, and an
optional bounded self-optimization cycle that can apply fixes in a
constrained, auto-fixable subset of findings.

## Why this exists

AI-generated code fails in characteristic ways that don't show up in a
normal lint/test pass: a plausible-looking but nonexistent package name,
a test that executes a code path without actually asserting anything
meaningful about it, a docstring or type hint that quietly drifted from
what the function now does, or an agent/skill definition with an
unbounded retry loop and no way to escalate. confab looks specifically
for these four failure modes, treats every finding as unconfirmed until
an independent verification pass re-checks it, and never lets a timeout
or an unreachable registry masquerade as a real verdict in either
direction.

## Install

```
/plugin install confab@<marketplace>
```

or, for local development, point Claude Code at this directory as a
plugin source.

<!-- rrt:auto:start:example-prompts-intro -->
## Example Prompts

Say any of these to Claude Code once the plugin is installed — they're plain-language
prompts, not exact phrasing Claude has to match. Claude routes them to the skill below
by intent.
<!-- rrt:auto:end:example-prompts-intro -->

##### Check for hallucinated dependencies

````prompt
"check if any of our dependencies are hallucinated"
````

> Triggers `confab-dependency-audit` — flags package names that don't exist in the
> real registry, independently re-verified before being reported.

##### Check test strength

````prompt
"would our tests actually catch a bug here?"
````

> Triggers `confab-assertion-audit` — mutation-testing pass checking whether tests
> assert anything meaningful, not just execute the code.

##### Run the full cycle

````prompt
"run the confab cycle on this repo"
````

> Triggers `confab-cycle` — bounded self-optimization loop: re-runs all four audits
> pass by pass, optionally applying fixes, until convergence.

##### Check status

````prompt
"where does confab stand on this repo"
````

> Triggers `confab-status` — read-only dashboard: what's run, what's stale, what to
> run next.

Run `confab-preflight` first if you're not sure the plugin's checks can even run in
this repo — it's read-only and never blocks the other four.

## Skills (8)

| Skill | What it does |
|---|---|
| `confab-preflight` | Five independent readiness checks; four per-domain readiness verdicts. |
| `confab-dependency-audit` | Flags hallucinated / typosquat-adjacent manifest dependencies via bounded, read-only registry lookups. |
| `confab-assertion-audit` | Mutation-testing pass (real tool if available, else LLM-reasoned) to check whether tests would actually catch bugs. |
| `confab-contract-drift` | Flags drift between type hints/signatures/docstrings/schemas and actual usage. |
| `confab-agentic-reliability` | Audits this repo's own skill/agent/workflow files for four reliability defect categories. |
| `confab-code-change` | Fast, changed-files-scoped advisory pass, for a pre-commit sanity check. |
| `confab-cycle` | Bounded self-optimization loop: re-runs audits pass by pass, optionally applying fixes, until convergence or a pass cap. |
| `confab-status` | Read-only dashboard: what's run, what's stale, what to run next. |

## Agents (5)

`dependency-auditor`, `assertion-auditor`, `contract-auditor`,
`agentic-reliability-auditor` each do the Find/Verify judgment work for
their domain and cannot write or modify files (enforced by their `tools:`
frontmatter — none of them has `Write` or `Edit`). `confab-remediator` is
the only agent with `Edit`, and only ever receives one already-located,
already-scoped finding at a time.

## How enforcement works (not just documentation)

Every MUST-NOT / refuse / halt rule in this plugin's behavioral spec is
enforced by code that can actually refuse, not by a sentence a model
reads and might still violate:

- **`scripts/lib/constants.py`** — every numeric bound (registry timeout,
  max cycle passes, max reopens) is a named constant with a hard ceiling,
  not a number quoted in prose.
- **`scripts/lib/schema.py`** — the shared finding schema
  (`severity`/`title`/`evidence`/`category`/`fixability`) is validated on
  every write, for every domain; a finding missing a gating field is
  dropped with a warning, never repaired or defaulted.
- **`scripts/lib/ledger.py`** — `confab-cycle`'s pass cap and reopen
  thrash-guard are enforced by functions that raise
  (`CycleBoundExceededError`) rather than loop conditions a session could
  misjudge.
- **`scripts/lib/paths.py`** — every write this plugin makes is validated
  against path traversal and absolute-path escapes before it happens,
  both for `analysis/confab/` output and for remediation targets inside the repo.
- **`scripts/lib/registry.py`** — a registry timeout can only ever
  produce `"skipped"`; there is no code path from a timeout to an
  affirmative "hallucinated" or "exists" verdict.
- **`hooks/hooks.json`** — two `PreToolUse` command hooks
  (`scripts/hooks/guard_edit_scope.py`, `scripts/hooks/guard_bash_scope.py`)
  enforce `confab-remediator`'s one-fix-per-finding scope and the
  fixable/draft-only domain split, and refuse install/publish/patch-mode
  Bash commands from the audit agents — regardless of whether the agent's
  own system prompt is followed. Both hooks are inert (exit 0) unless the
  target repository already has a `analysis/confab/` directory, and both fail
  closed on any internal error, naming an explicit escape hatch in the
  denial message.

## Design decisions (spec was silent on these)

The behavioral spec stated obligations, not implementation details. Where
it didn't specify something, these are the choices made and why:

- **Output location**: all confab artifacts live under `analysis/confab/` at the
  repo root (`reports/*.md` for the human-readable outputs,
  `*_summary.json` sidecars, `ledger.json`, a `symbol_index/` snapshot
  cache, and a transient `remediation_scope.json` lock). The spec named
  filenames like `DEPENDENCY_AUDIT.md` without a directory; putting
  everything under one declared directory is what makes the write-scope
  enforcement in `lib/paths.py` possible and keeps the repo root clean.
- **First-pass constraint-domain tiebreak in `confab-cycle`**: when the
  ledger has no findings yet (first pass of a fresh cycle), there's no
  "most open High findings" signal to rank domains by. `cycle_engine.py`
  falls back to a fixed canonical order: `dependency_audit`,
  `contract_drift`, `agentic_reliability`, `assertion_audit` — roughly
  cheapest/fastest-to-check first.
- **`confab-code-change`'s per-domain checks are single-pass, unverified**:
  the spec's guarantee for this skill is "verdict always advisory," not
  "verification always runs" — unlike the four full domain-audit skills,
  a fast pre-commit check trades verification rigor for speed. If a user
  wants a verified result, the README and the skill's own instructions
  point them at the corresponding full `confab-*-audit` skill instead.
- **Typosquat heuristic**: `dependency_audit.py` ships a small seed list
  of well-known packages per ecosystem and a Levenshtein-distance-1
  check. This is a first-pass heuristic, not an oracle — the
  `dependency-auditor` agent can supply additional judgment-based
  candidates (e.g. names engineered to look official) via
  `--agent-findings`, which get the same mandatory independent re-check
  as script-found candidates.
- **Symbol-index snapshot format**: left as an opaque JSON blob the
  building agent/script controls the shape of; `lib/symbol_index.py` only
  enforces the build-once-per-invocation, single-flight-lock behavior,
  not a specific schema for the index contents, since the spec doesn't
  define one and the two consumers (`contract-auditor`, `assertion-auditor`)
  have different evidence needs.
- **`confab-remediator`'s dispatch granularity**: the spec says "given a
  batch of findings" for the agent's `must_refuse` list but "exactly one
  scoped fix" for its role — resolved as: the *agent* is always dispatched
  once per finding (never handed a batch to iterate itself), and
  `confab-cycle` is the one that iterates the batch across separate
  dispatches. This is what makes the `PreToolUse` scope hook viable: it
  only ever has to reason about one active scope at a time.

## Requirements

Python 3.9+ (stdlib only — no third-party dependencies for any enforcement
script). Network access is required for `confab-dependency-audit`'s
registry lookups and `confab-preflight`'s reachability check; both are
read-only GET requests bounded by a timeout and degrade to `"skipped"`
rather than failing the run when network access isn't available.
