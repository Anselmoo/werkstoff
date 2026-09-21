# zeugnis

**Audits AI-generated code quality across four independent domains —
hallucinated dependencies, weak test assertions, contract drift, and
agentic-loop reliability — with independent verification, and an
optional bounded self-optimization cycle that can apply fixes in a
constrained, auto-fixable subset of findings.**

A *Zeugnis* is the mill certificate — the EN 10204 *Werkszeugnis* or
*Abnahmepruefzeugnis* in which a supplier declares what a material actually is. Its
grades are the point: 2.1 is the supplier's own word, 3.1 is their own inspector, and
3.2 requires an independent one. A claim is worth what the party behind it is worth.
That is this plugin's rule — no finding counts until a pass that did not produce it
re-checks it, which is why every audit here has a separate Verify phase.

## Why this exists

AI-generated code fails in characteristic ways that don't show up in a
normal lint/test pass: a plausible-looking but nonexistent package name,
a test that executes a code path without actually asserting anything
meaningful about it, a docstring or type hint that quietly drifted from
what the function now does, or an agent/skill definition with an
unbounded retry loop and no way to escalate. zeugnis looks specifically
for these four failure modes, treats every finding as unconfirmed until
an independent verification pass re-checks it, and never lets a timeout
or an unreachable registry masquerade as a real verdict in either
direction.

## What it is not

zeugnis's four audits are narrow by design. Two adjacent jobs are
explicitly out of scope and deferred to sibling plugins:

- **Not a prose-documentation-drift checker.** `zeugnis-contract-drift`'s
  scope is "structural, machine-checkable declarations only" — type
  hints, docstrings, and API/OpenAPI/GraphQL schemas against real
  call-site or handler usage. A claim in `CLAUDE.md`, `README.md`,
  `ARCHITECTURE.md`, `DECISIONS.md` or an ADR file no longer matching the
  code is `befund:befund-docs-drift`'s job, not zeugnis's.
- **Not a verifier of a specific change, fix, wire, or numeric claim.**
  `zeugnis-assertion-audit` judges only whether the *tests* would catch a
  bug — it is explicitly "not for proving that a specific change, fix,
  wire, or numeric claim is correct." That adversarial verification is
  `andon:andon-verify`'s job.

## Install

```
/plugin marketplace add Anselmoo/werkstoff
/plugin install zeugnis@werkstoff
```

Both `PreToolUse` hooks are inert until the target repository already has
an `analysis/zeugnis/` directory, so installing the plugin changes nothing
until a zeugnis audit skill has actually run once.

### Requirements

Python 3.9+ (stdlib only — no third-party dependencies for any enforcement
script). Network access is required for `zeugnis-dependency-audit`'s
registry lookups and `zeugnis-preflight`'s reachability check; both are
read-only GET requests bounded by a timeout and degrade to `"skipped"`
rather than failing the run when network access isn't available.

### Local development

Point Claude Code at a checkout without registering the marketplace:

```bash
claude --plugin-dir /path/to/werkstoff/plugins/zeugnis
```

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

> Triggers `zeugnis-dependency-audit` — flags package names that don't exist in the
> real registry, independently re-verified before being reported.

##### Check test strength

````prompt
"would our tests actually catch a bug here?"
````

> Triggers `zeugnis-assertion-audit` — mutation-testing pass checking whether tests
> assert anything meaningful, not just execute the code.

##### Run the full cycle

````prompt
"run the zeugnis cycle on this repo"
````

> Triggers `zeugnis-cycle` — bounded self-optimization loop: re-runs all four audits
> pass by pass, optionally applying fixes, until convergence.

##### Check status

````prompt
"where does zeugnis stand on this repo"
````

> Triggers `zeugnis-status` — read-only dashboard: what's run, what's stale, what to
> run next.

##### Check for contract drift

````prompt
"check if our type signatures and docstrings still match how the code is actually called"
````

> Triggers `zeugnis-contract-drift` — compares type hints, docstrings, and
> API/OpenAPI/GraphQL schemas against real call-site or handler usage,
> independently re-verified by default.

##### Audit the plugin's own agent design

````prompt
"is our own agent design safe — any unbounded retries or missing escalation paths?"
````

> Triggers `zeugnis-agentic-reliability` — audits this repo's own skill/agent/workflow
> definitions for unbounded retry loops, unwired Find/Verify phases, and excessive
> tool grants.

##### Quick pre-commit check

````prompt
"is this diff okay to commit?"
````

> Triggers `zeugnis-code-change` — runs only the domains whose file patterns match
> what actually changed, and always produces an advisory verdict that never blocks
> the commit.

##### Check readiness first

````prompt
"is zeugnis set up correctly in this repo?"
````

> Triggers `zeugnis-preflight` — five independent readiness checks, one verdict per
> domain skill, before any audit actually runs.

Run `zeugnis-preflight` first if you're not sure the plugin's checks can even run in
this repo — it's read-only and never blocks the other four.

## Components

### Skills (8)

| Skill | What it does |
|---|---|
| `zeugnis-preflight` | Five independent readiness checks; four per-domain readiness verdicts. |
| `zeugnis-dependency-audit` | Flags hallucinated / typosquat-adjacent manifest dependencies via bounded, read-only registry lookups. |
| `zeugnis-assertion-audit` | Mutation-testing pass (real tool if available, else LLM-reasoned) to check whether tests would actually catch bugs. |
| `zeugnis-contract-drift` | Flags drift between type hints/signatures/docstrings/schemas and actual usage. |
| `zeugnis-agentic-reliability` | Audits this repo's own skill/agent/workflow files for four reliability defect categories. |
| `zeugnis-code-change` | Fast, changed-files-scoped advisory pass, for a pre-commit sanity check. |
| `zeugnis-cycle` | Bounded self-optimization loop: re-runs audits pass by pass, optionally applying fixes, until convergence or a pass cap. |
| `zeugnis-status` | Read-only dashboard: what's run, what's stale, what to run next. |

### Agents (5)

`dependency-auditor`, `assertion-auditor`, `contract-auditor`,
`agentic-reliability-auditor` each do the Find/Verify judgment work for
their domain and cannot write or modify files (enforced by their `tools:`
frontmatter — none of them has `Write` or `Edit`). `zeugnis-remediator` is
the only agent with `Edit`, and only ever receives one already-located,
already-scoped finding at a time.

## What is enforced, and what is not

### How enforcement works (not just documentation)

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
- **`scripts/lib/ledger.py`** — `zeugnis-cycle`'s pass cap and reopen
  thrash-guard are enforced by functions that raise
  (`CycleBoundExceededError`) rather than loop conditions a session could
  misjudge.
- **`scripts/lib/paths.py`** — every write this plugin makes is validated
  against path traversal and absolute-path escapes before it happens,
  both for `analysis/zeugnis/` output and for remediation targets inside the repo.
- **`scripts/lib/registry.py`** — a registry timeout can only ever
  produce `"skipped"`; there is no code path from a timeout to an
  affirmative "hallucinated" or "exists" verdict.
- **`hooks/hooks.json`** — two `PreToolUse` command hooks
  (`scripts/hooks/guard_edit_scope.py`, `scripts/hooks/guard_bash_scope.py`)
  enforce `zeugnis-remediator`'s one-fix-per-finding scope and the
  fixable/draft-only domain split, and refuse install/publish/patch-mode
  Bash commands from the audit agents — regardless of whether the agent's
  own system prompt is followed. Both hooks are inert (exit 0) unless the
  target repository already has a `analysis/zeugnis/` directory, and both fail
  closed on any internal error, naming an explicit escape hatch in the
  denial message.

## The report

`scripts/build_burndown_html.py` renders `ledger.json`'s recorded pass
history into a self-contained HTML report (`analysis/zeugnis/reports/BURNDOWN.html`
by default) with a Trend tab and a Breakdown tab. The Trend tab is the
default view — a single honest D3 line chart of cumulative closed
findings, since `ledger.json`'s `passes` array is the only place
pass-over-pass history actually exists:

![Zeugnis burndown viewer: a "Has this cleanup converged?" panel whose verdict reads that the cleanup has NOT converged — 1 finding escalated, 1 open, the last pass closed 0 — above a four-item legend naming closed, open, escalated and the cumulative-closed trend line with a swatch and a glyph each; a tile row reading 5 total passes, 10 findings tracked, 1 open (amber-outlined), 8 closed and 1 escalated (red-outlined, "needs a human"); and the Trend tab's single D3 line of cumulative closed findings climbing across five passes and flattening at the last](assets/burndown-viewer-screenshot.jpg)

The Breakdown tab adds by-status and by-domain bars plus a findings
sidebar, drawn from `ledger.json`'s current-snapshot `findings` map.

That image is reproducible rather than a one-off capture — the ledger it
shows is committed at `scripts/fixtures/sample_burndown_ledger.json` (5
passes and 10 findings, chosen so the last pass closes nothing and one
finding sits `escalated` with `reopenCount: 4` — the thrash-guard
outcome this plugin exists to surface, and the one status that never
clears itself). To rebuild it:

```bash
mkdir -p /tmp/zeugnis-demo/analysis/zeugnis
cp plugins/zeugnis/scripts/fixtures/sample_burndown_ledger.json \
    /tmp/zeugnis-demo/analysis/zeugnis/ledger.json
python3 plugins/zeugnis/scripts/build_burndown_html.py /tmp/zeugnis-demo \
    --template plugins/zeugnis/assets/burndown-viewer.html \
    --d3 plugins/zeugnis/assets/inline-d3.html \
    --tokens plugins/zeugnis/assets/tokens.css
```

The report states its own verdict in words before any chart: whether the
cleanup converged, stalled, or is still closing findings, and what an
escalated finding means. Every status colour is named in a legend that is
visible without clicking anything, because `--status-good`/`--status-bad`
are not separable under deuteranopia — see the mandate at the top of
`tools/design-tokens/tokens.css`.

## Design decisions

*(spec was silent here)*

The behavioral spec stated obligations, not implementation details. Where
it didn't specify something, these are the choices made and why:

- **Output location**: all zeugnis artifacts live under `analysis/zeugnis/` at the
  repo root (`reports/*.md` for the human-readable outputs,
  `*_summary.json` sidecars, `ledger.json`, a `symbol_index/` snapshot
  cache, and a transient `remediation_scope.json` lock). The spec named
  filenames like `DEPENDENCY_AUDIT.md` without a directory; putting
  everything under one declared directory is what makes the write-scope
  enforcement in `lib/paths.py` possible and keeps the repo root clean.
- **First-pass constraint-domain tiebreak in `zeugnis-cycle`**: when the
  ledger has no findings yet (first pass of a fresh cycle), there's no
  "most open High findings" signal to rank domains by. `cycle_engine.py`
  falls back to a fixed canonical order: `dependency_audit`,
  `contract_drift`, `agentic_reliability`, `assertion_audit` — roughly
  cheapest/fastest-to-check first.
- **`zeugnis-code-change`'s per-domain checks are single-pass, unverified**:
  the spec's guarantee for this skill is "verdict always advisory," not
  "verification always runs" — unlike the four full domain-audit skills,
  a fast pre-commit check trades verification rigor for speed. If a user
  wants a verified result, the README and the skill's own instructions
  point them at the corresponding full `zeugnis-*-audit` skill instead.
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
- **`zeugnis-remediator`'s dispatch granularity**: the spec says "given a
  batch of findings" for the agent's `must_refuse` list but "exactly one
  scoped fix" for its role — resolved as: the *agent* is always dispatched
  once per finding (never handed a batch to iterate itself), and
  `zeugnis-cycle` is the one that iterates the batch across separate
  dispatches. This is what makes the `PreToolUse` scope hook viable: it
  only ever has to reason about one active scope at a time.

## Verifying a change to this plugin

```bash
python3 plugins/zeugnis/scripts/hooks/test_guard_edit_scope.py   # the edit-scope hook denies AND allows (8 cases)
python3 plugins/zeugnis/scripts/test_build_burndown_html.py      # burndown HTML renderer, known fixtures
python3 plugins/zeugnis/scripts/test_cycle_engine.py             # pass cap / reopen thrash-guard raise correctly
python3 test/plugins/lint-frontmatter.py plugins/zeugnis         # YAML that would load with EMPTY metadata
python3 test/plugins/verify-hooks-deny.py plugins/zeugnis        # both hooks deny the violation AND stay inert elsewhere
claude plugin validate plugins/zeugnis --strict                  # manifest + structure
python3 plugins/nacharbeit/scripts/nacharbeit_lint.py plugins/zeugnis --docs-root docs   # mechanical M/H/S/A/P/D rules
```

There is no `guard_bash_scope.py`-specific unit test file — its behavior
is covered by `test/plugins/verify-hooks-deny.py` (declared-command
resolution against a crafted violating Bash event) rather than a
dedicated `unittest` module.

### Behavioural cases

```bash
bash test/plugins/verify-clean-box.sh        # ALWAYS first
bash test/plugins/run.sh new-dep-audit       # zeugnis-dependency-audit against a seeded hallucinated package
```

## Escape hatch

Both hooks fail closed and always name their own bypass in the deny
message:

- **`guard_edit_scope.py`** (Edit/Write): "If this edit is unrelated to a
  zeugnis remediation, remove `analysis/zeugnis/remediation_scope.json`
  (or the whole `analysis/zeugnis/` directory) to clear stuck state, or
  run `zeugnis-cycle` without `--fix`."
- **`guard_bash_scope.py`** (Bash): "If this command is genuinely needed
  and unrelated to a zeugnis audit, run it outside a zeugnis-managed
  session, or remove `analysis/zeugnis/` from this repository to disable
  this guard."

Both hooks are also inert by construction — see "What is enforced, and
what is not" — until the target repository already has an
`analysis/zeugnis/` directory, so a repo that has never run a zeugnis
skill is never touched by either guard.
