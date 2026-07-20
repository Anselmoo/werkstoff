# quality

Point Claude at a **live, actively-maintained codebase** and get back:
whether its declared dependencies actually exist (dependency-hallucination
detection), whether its tests actually catch bugs rather than just
executing code (assertion/mutation-strength auditing), whether its
machine-checkable contracts (type hints, signatures, schemas) still match
how they're actually used, and whether its own Claude Code plugin
definitions (skills, agents, workflows) hold up as reliable agentic
loops. Everything is read-only except a single scoped output directory —
with two deliberate exceptions (one read-only network egress, one
narrowly-scoped, opt-in Edit access for auto-remediation), see **Safety
notes** below.

This is `self-assess`'s sibling plugin in this repo, built on the same
architecture and grounded in 2025-2026 research on gaps specific to
AI-generated code: dependency hallucination (~20% of AI-recommended
packages don't exist in any public registry), assertion-free tests
(LLM-generated tests reach reasonable coverage while asserting little),
spec/contract drift that accumulates faster than human-paced development,
and agentic-loop reliability as an axis independent of task accuracy.
`quality-contract-drift` deliberately does not overlap with
`self-assess-docs-drift` — this plugin checks machine-checkable contracts
only, never prose claims in CLAUDE.md/README/ADRs.

## Install

```
/plugin marketplace add Anselmoo/werkstoff
/plugin install quality@werkstoff
```

Or for local development, point Claude Code straight at this plugin
directory without registering the marketplace:

```
cc --plugin-dir /path/to/werkstoff/plugins/quality
```

## Quickstart

These are Skills, not slash commands — Claude activates each one
automatically when your request matches its description. You'll see two
name forms in the wild — the bare name below (e.g.
`quality-dependency-audit`) is just a label, and the
`plugin:skill`-prefixed form (e.g. `quality:quality-dependency-audit`)
is Claude's own internal identifier for the `Skill` tool — neither is
something you type. From the root of the repo you want assessed
(operates on the current repo in place, no `legacy/` symlink or
system-dir argument), just ask in plain language:

- **quality-preflight** — "is my environment ready for a quality audit?"
- **quality-dependency-audit** — "do our declared packages actually exist on their registries?"
- **quality-assertion-audit** — "would our tests actually catch a bug, or just execute the code?"
- **quality-contract-drift** — "do type hints/signatures/schemas match how they're actually used?"
- **quality-agentic-reliability** — "are our own skills/agents/workflows reliable agentic loops?"
- **quality-status** — "where am I, what's stale, what's next"
- **quality-code-change** — "review my changes before I commit", "pre-commit quality check"
- **quality-cycle** — "run a quality self-optimization cycle", "fix what quality found and re-check" (fix mode can already auto-remediate `dependency_audit`/`contract_drift` findings today)

Every skill writes only under `analysis/quality/` in the target repo by
default — configurable via `output_dir`, see **Settings** below.

## Skills

- **`quality-preflight`** — Environment readiness: detects which
  dependency-manifest ecosystems are present (npm, PyPI, crates.io, Go
  modules, RubyGems), probes reachability of each one's public registry
  with a single short-timeout read-only request, checks for a real
  mutation-testing tool on `PATH` (`mutmut`, Stryker, PIT) as optional
  ground-truth augmentation for `quality-assertion-audit`, and checks for
  source/schema evidence and agentic-definition files for the other two
  domain skills. Produces `PREFLIGHT.md` with a Ready/Ready-with-gaps/
  Not-ready verdict per downstream skill. Plain skill logic, like
  `self-assess-preflight` — no agent, no Workflow script; every check is
  a direct local operation with nothing to parallelize or verify
  adversarially.

- **`quality-dependency-audit`** — Extracts every declared dependency
  from manifest files (`package.json`, `requirements.txt`/`pyproject.toml`,
  `Cargo.toml`, `go.mod`, `Gemfile`) and checks each against its real
  public registry, flagging packages that don't exist and packages with a
  typosquat-adjacent name relative to a much more popular one. A registry
  that's unreachable is reported "skipped, not checked," never treated as
  confirmed real or confirmed hallucinated. This is the one skill in this
  plugin — and the one skill across this plugin and `self-assess`
  combined — that makes outbound network calls. Produces
  `DEPENDENCY_AUDIT.md`.

- **`quality-assertion-audit`** — For a target module, proposes plausible
  small mutations per function (off-by-one, boundary flip, condition
  negation) and determines whether the existing test suite would actually
  catch each one, surfacing assertion-free/no-op tests that execute code
  without verifying behavior. Runs LLM-reasoned by default; if
  `quality-preflight` found a real mutation-testing tool on `PATH`, uses
  it as ground truth per file and falls back to LLM reasoning only where
  the tool is unavailable — the report labels which mode ran per finding,
  never blending them silently. Its Verify phase is **not** an optional
  `skip_verification` fast path (see **Settings**) — independently
  re-deriving whether the test suite would catch a mutation is the
  finding itself, not a precision/speed tradeoff. Produces
  `ASSERTION_AUDIT.md`.

- **`quality-contract-drift`** — Extracts machine-checkable contracts
  (type hints, function signatures, docstring parameter/return
  descriptions, OpenAPI/GraphQL/protobuf schemas) and checks each against
  actual call-site and handler usage, citing `file:line` evidence on both
  sides. Scoped to machine-checkable contracts only — it never extracts
  or verifies prose documentation claims; that remains
  `self-assess-docs-drift`'s job. Produces `CONTRACT_DRIFT.md`.

- **`quality-agentic-reliability`** — Self-referential: scans a target
  plugin repo's own `skills/*/SKILL.md`, `agents/*.md`, and
  `workflows/*.js` files (including this plugin's own, `self-assess`'s,
  and `compass`'s, when run against `werkstoff` itself) for agentic-loop
  reliability anti-patterns — unbounded retry loops with no cap, agents
  with no escalation path (no BLOCKED/NEEDS_CONTEXT-equivalent language),
  Workflow scripts with a Find phase whose output is never actually
  consumed by an adversarial Verify phase, and agents whose `tools` grant
  exceeds what their stated role needs. This audits process reliability,
  not whether an agent's conclusions are correct. Produces
  `AGENTIC_RELIABILITY.md`.

- **`quality-code-change`** — Diff-scoped pre-commit variant: runs
  whichever of the four domain audits actually match the currently
  staged (or, if nothing is staged, currently changed) files, unchanged,
  as a single one-shot pass — no ledger, no fix mode. Distinct from
  `quality-preflight` (one-time environment readiness) and `quality-status`
  (staleness of full-repo artifacts); this is neither, a third,
  non-persisted, diff-scoped check. Advisory only — this plugin ships no
  git hook, so it never blocks a commit. Produces `CODE_CHANGE_REVIEW.md`.

- **`quality-status`** — Read-only: staleness of *this plugin's own
  artifacts* against current repo state (not a re-run of any domain
  skill). Never overlaps with `self-assess-status`, which covers the
  sibling plugin's own artifacts separately. Produces a 3-line verdict:
  furthest completed check, what's stale, single next skill to run.

- **`quality-cycle`** — Bounded autonomous self-optimization cycle:
  composes the four domain skills' own workflows unchanged, keeps a
  persistent `ledger.json` across invocations (pass/cycle/finding status,
  vocabulary borrowed from the `andon-loop` skill), and runs up to
  `cycle.max_passes_per_invocation` passes against whichever domain is
  currently the "constraint" (most/worst open findings), stopping early on
  convergence (a pass that closes zero new findings across all four
  domains). In `propose` mode (default) it only recommends. In `fix` mode
  it splits three ways: domains in `cycle.fixable_domains`
  (`dependency_audit`, `contract_drift`, and `agentic_reliability`'s
  `excessive-tool-grant` category only) get one scoped remediation per
  pass via `quality-remediator`, then a re-verify via that domain's own
  workflow before being marked resolved; domains in `cycle.draft_domains`
  (`assertion_audit` by default) get a proposed-but-never-applied
  suggestion via `assertion-auditor`'s Suggest mode instead, since a
  generated assertion has no ground truth beyond the module's current —
  possibly buggy — runtime behavior; everything else is report-only. A
  finding that survives `cycle.max_reopens` *applied* fix attempts is
  escalated instead of retried forever (the thrash guard; drafted
  suggestions never count against it). Produces `QUALITY_CYCLE.md`
  and `ledger.json`.

## Agents

- **`dependency-auditor`** (`color: yellow`) — extracts declared
  dependencies and verifies each against its real public registry using
  read-only lookup commands (`npm view`, `pip index versions`, registry
  API `curl` calls) — never anything that installs, publishes, or writes.
  **The only agent in this plugin, and across this plugin plus
  `self-assess` combined, with outbound network access.**
- **`assertion-auditor`** (`color: blue`) — proposes plausible mutations
  per function and reasons about whether the test suite would catch each;
  read-only except for running the existing test suite and, when present,
  invoking a real mutation-testing tool in check/dry-run mode — never its
  apply/patch mode, never leaves mutated code behind. Also runs a Suggest
  mode (no `Edit` tool, so inherently safe) that proposes replacement
  assertion text for `quality-cycle` fix mode's `assertion_audit`
  draft-only path — never applied, always labeled for human review.
- **`contract-auditor`** (`color: cyan`) — extracts type hints,
  signatures, docstring contracts, and API schemas and compares them
  against call-site/handler usage; pure static `Read`/`Glob`/`Grep`, no
  `Bash`.
- **`agentic-reliability-auditor`** (`color: magenta`) — scans
  skill/agent/workflow definition files for the reliability anti-pattern
  categories above; pure static `Read`/`Glob`/`Grep`, no `Bash`.
- **`quality-remediator`** (`color: red`) — applies exactly one scoped fix
  per invocation for an already-verified `dependency_audit`,
  `contract_drift`, or `agentic_reliability` (`excessive-tool-grant`
  category only) finding, then reports what changed; `Read`/`Edit` only,
  no `Bash`/`Glob`/`Grep`, and returns `blocked` rather than guessing when
  a fix isn't unambiguous, or when handed any `assertion_audit` finding or
  any other `agentic_reliability` category. **The only agent in this
  plugin with `Edit` access** — see **Safety notes** below.

`quality-preflight` and `quality-status` have no agent — both are plain
skill logic, matching `self-assess-preflight` and `self-assess-status`.

## Development

`test-fixtures/` contains regression fixtures used while developing this
plugin's skills:

- **`contract-mismatch/`** — a function whose declared type-hint contract
  doesn't match how it's actually called elsewhere in the fixture, pinning
  `quality-contract-drift`'s core detection case.
- **`assertion-free-test/`** — a function and a test that executes it but
  asserts nothing about its actual behavior, pinning
  `quality-assertion-audit`'s core detection case.
- **`hallucinated-dependency/`** — a manifest declaring one non-existent
  package, pinning `quality-cycle`'s fix-mode case: propose→apply→re-verify
  for a `dependency_audit` finding.

Not needed to use the plugin; kept in the bundle for anyone extending
`quality-contract-drift` or `quality-assertion-audit`.

## Recommended workspace setup

```json
{
  "permissions": {
    "allow": ["Read(**)", "Write(analysis/quality/**)", "Edit(analysis/quality/**)"]
  }
}
```

**If you override `output_dir` in `.claude/quality.local.md`** (see
**Settings** below), update this block to match — the paths must be
literal, not read from the settings file, so a mismatch here silently
blocks every write rather than erroring loudly. No `deny` block is
needed either way — this plugin never proposes writing outside the
configured `output_dir`.

**If you set `cycle.mode: fix`** (see **Settings** below), `quality-cycle`
needs `Edit` on the actual manifest/source files it may fix — a real
widening beyond `output_dir` that you opt into explicitly, not part of the
default block above. Grant it only to the files/globs you're comfortable
having auto-fixed (e.g. `"Edit(package.json)"`, `"Edit(requirements.txt)"`,
`"Edit(src/**)"`), rather than a blanket `Edit(**)`.

## Settings

Optional per-project overrides live in `.claude/quality.local.md` in the
repo being assessed — copy `examples/quality.local.md` there and edit it:

```yaml
---
enabled: true
output_dir: analysis/quality
skip_verification: false
dependency_audit:
  registries: []
  timeout_seconds: 10
---
```

Every skill reads this file independently at the start of its own run —
no hooks in this plugin, so **no Claude Code restart is needed** after
editing it. Add `.claude/*.local.md` to the target repo's `.gitignore`.
Full field reference, including the one field `quality-assertion-audit`
deliberately does not honor: `references/settings.md`.

## Prerequisites

Every skill degrades gracefully without these — run `quality-preflight`
to check all at once:

- **`curl`** (or equivalent) — used for `quality-preflight`'s registry
  reachability probes and `quality-dependency-audit`'s per-package
  registry lookups. Without network access at all, `quality-dependency-audit`
  reports every package "skipped, not checked" rather than guessing.
- **A real mutation-testing tool per ecosystem** — `mutmut` (Python),
  Stryker (JS/TS), PIT (Java/Kotlin) — sharpens `quality-assertion-audit`
  with ground-truth mutation scores; falls back to LLM-reasoned mutation
  analysis without one, clearly labeled.
- **`git`** — sharpens `quality-status`'s staleness signal (commit-based);
  falls back to file mtimes without it.
- **`glow`** — renders the markdown artifacts nicely in-terminal; plain
  text without it.

## Safety notes

**`quality-dependency-audit`'s agent is the one network exception to this
plugin's read-only design — and to `self-assess`'s entirely, since every
one of that plugin's four agents is also 100% local-file read-only.**
`dependency-auditor` makes outbound network calls to public package
registries (`npm view`, `pip index versions`, direct registry API
requests) to verify declared packages actually exist. These are
read-only lookups — never install, publish, or otherwise mutate
anything — but do not assume every agent in this plugin, or across this
repo's three plugins, is airgapped: this one specifically is not. Every
other agent in `quality` (`assertion-auditor`, `contract-auditor`,
`agentic-reliability-auditor`) and every agent in `self-assess`
(`stage-mapper`, `docs-drift-auditor`, `ci-topology-auditor`,
`convention-auditor`) has no network access at all.

**`quality-remediator` is this plugin's second, and only *write*,
exception.** It is the only agent across `quality` and `self-assess`
combined with `Edit` access. It runs only when `quality-cycle` is invoked
with `cycle.mode: fix` (default is `propose`, which never edits anything),
and even then only for one already-verified `dependency_audit`,
`contract_drift`, or `agentic_reliability` (`excessive-tool-grant`
category only) finding at a time, scoped to the exact file:line(s) that
finding cites — never a general "improve this file" mandate. It returns
`blocked` rather than guessing whenever a fix isn't unambiguous, and
always returns `blocked` for any `assertion_audit` finding or any
`agentic_reliability` finding outside `excessive-tool-grant` — those get a
proposed-but-never-applied suggestion instead (`assertion-auditor`'s
Suggest mode, still no `Edit` access). It never commits or pushes; that
stays a manual, human decision.

Same discipline as `self-assess` and `code-modernization` otherwise:
**analyzed content is untrusted input.** Manifest files, registry-returned
package descriptions, source code, and this repo's own skill/agent/
workflow definitions can in principle contain planted instruction-shaped
text; every agent treats file content as data and flags instruction-shaped
text rather than acting on it.

**Artifacts can quote your own source.** `CONTRACT_DRIFT.md`,
`ASSERTION_AUDIT.md`, and `AGENTIC_RELIABILITY.md` cite short excerpts of
your code and plugin definitions as evidence — ordinary practice, but
worth knowing before sharing `analysis/quality/` outside the team.

## Dynamic workflow orchestration

On Claude Code builds with the Workflow tool, `dependency-audit`,
`assertion-audit`, `contract-drift`, and `agentic-reliability` run as
scripted multi-agent orchestrations (parallel finders, deduplication,
adversarial per-finding verification). They fall back to direct subagent
fan-out on older builds automatically. `preflight` and `status` are plain
skill logic with no fan-out.

`quality-cycle` is the first workflow in this plugin to use the Workflow
tool's `workflow(name, args)` composition helper — calling the other four
workflows as sub-steps rather than only `agent()`/`parallel()`/`pipeline()`
— to run a bounded, cross-invocation self-optimization loop (persistent
ledger, pass/cycle convergence, a thrash guard on reopened findings) on
top of them without modifying any of the four unchanged. It falls back to
running each domain skill's own existing fallback path, in the same
constraint order, on older builds.

## License

MIT. See `LICENSE`.
