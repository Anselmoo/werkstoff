# self-assess

Point Claude at a **live, actively-maintained codebase** — not a legacy
system being archaeologically rebuilt — and get back: an import-graph-based
map of its real architectural boundaries, a report of where its own docs
(CLAUDE.md, ADRs, DECISIONS.md, README) have drifted from what the code
actually does, an audit of its git/CI topology, and a check against its own
stated conventions. Almost everything is read-only except a single scoped
output directory — with two deliberate, tightly-gated exceptions
(`self-assess-transform-execute`'s and `self-assess-idiom-fix`'s
narrowly-scoped Edit access, both off by default), see **Safety notes**
below.

Where [`code-modernization`](https://github.com/anthropics/claude-plugins-official)
assumes `legacy/<system>/` is being discovered and rebuilt into
`modernized/<system>/`, this plugin assumes the opposite: the repo owner
already knows their system, the docs are evidence rather than a discovery
target, and there is nothing to migrate — only drift to catch. It reuses
`code-modernization`'s proven mechanics (Ready/Ready-with-gaps/Not-ready
preflight, staleness-comparison status, parallel-finder + adversarial-verify
Workflow scripts, ecosystem-tool detection discipline) retargeted onto that
different shape.

## Install

```
/plugin marketplace add Anselmoo/werkstoff
/plugin install self-assess@werkstoff
```

Or for local development, point Claude Code straight at this plugin
directory without registering the marketplace:

```
cc --plugin-dir /path/to/werkstoff/plugins/self-assess
```

## Quickstart

These are Skills, not slash commands — Claude activates each one
automatically when your request matches its description. You'll see two
name forms in the wild — the bare name below (e.g.
`self-assess-stage-map`) is just a label, and the
`plugin:skill`-prefixed form (e.g. `self-assess:self-assess-stage-map`)
is Claude's own internal identifier for the `Skill` tool — neither is
something you type. From the root of the repo you want assessed (no
`legacy/` symlink, no system-dir argument — it operates on the current
repo in place), just ask in plain language:

- **self-assess-preflight** — "is my environment ready for self-assess?"
- **self-assess-stage-map** — "map the real import-graph stages/wires" (opens an interactive map)
- **self-assess-arch-health** — "find god-modules, dependency cycles, layering violations" (over the stage-map graph)
- **self-assess-transform-brief** — "what's the target architecture and how do we get there" (current→target 1:1/merge/split mapping, phased sequence, Mermaid exports)
- **self-assess-transform-execute** — "execute phase N of the modernization brief" (off by default — one of the plugin's two Edit exceptions, see Safety notes)
- **self-assess-docs-drift** — "where do CLAUDE.md/ADRs/README contradict the code?"
- **self-assess-ci-topology** — "check our git remotes, CI config, mirror scripts, commit signing for drift"
- **self-assess-lint-audit** — "does the code follow its own house-rules.md?"
- **self-assess-code-idiom** — "find deprecated idioms + generic code smells in the code itself"
- **self-assess-idiom-fix** — "apply the modernization findings from code-idiom" (off by default — the other of the plugin's two Edit exceptions, see Safety notes)
- **self-assess-extract-rules** — "mine the business rules out of this codebase" (Rule Cards, Given/When/Then)
- **self-assess-complexity-score** — "which module needs attention first?" (COCOMO/CCN tech-debt index)
- **self-assess-status** — "where am I, what's stale, what's next"
- **self-assess-portfolio** — "heat-map dashboard across many repos" (run from the parent dir)

Every skill writes only under `analysis/self-assess/` in the target repo
by default — configurable via `output_dir`, see **Settings** below.

## Skills

- **`self-assess-preflight`** — Environment readiness: detects the stack
  (languages present), checks analysis-tool availability, smoke-parses one
  representative file per detected language (proves the stage-map
  extractor will actually run), checks for `house-rules.md`, and checks
  git-remote/CI-config readability. Produces `PREFLIGHT.md` with a
  Ready/Ready-with-gaps/Not-ready verdict per downstream skill.

- **`self-assess-stage-map`** — Builds a real per-language import/use
  graph and clusters it into stages by **package boundary**, not manifest
  directory — the fix for the bug where two packages sharing one
  `pyproject.toml` collapse into a single stage. Detection and extraction
  are driven by [`references/language-support.md`](references/language-support.md),
  a single canonical table covering the 20 most common languages
  (Python, JS, TS, Java, C#, C++, C, Go, Rust, PHP, Ruby, Swift, Kotlin,
  Shell/Bash, PowerShell, R, Scala, Perl, Lua, Dart) with a
  manifest-based pass plus an extension-frequency fallback for
  manifest-less stacks (shell scripts and similar) — any other language
  still runs via a generic fallback rather than being silently skipped.
  Edge vocabulary borrows Kythe/LSIF's node-edge terms (`defines`, `ref`,
  `ref/call`, `childof`) for portability, without depending on Kythe/LSIF
  tooling itself. Produces `STAGE_MAP.md` and an interactive
  `STAGE_MAP.html` (reusing `code-modernization`'s topology viewer). Also
  persists the full graph as `stage_graph.json` for `self-assess-arch-health`.

- **`self-assess-arch-health`** — A new analysis pass over the stage/wire
  graph `self-assess-stage-map` already built (reads its `stage_graph.json`,
  never re-deriving the import graph), flagging **architecture deficiencies**
  as pass/fail findings: god-modules (a stage most others depend on — a
  bottleneck), circular dependencies between stages (a strongly-connected
  component that blocks independent build/test/release), and layering
  violations (a production stage importing a test-only/benchmark/fixture
  stage). Candidates are computed deterministically (degree thresholds,
  Tarjan SCC, production→test edges) then confirmed adversarially against the
  real code. Distinct from `self-assess-complexity-score`, which ranks stages
  by size and deliberately emits no findings. Produces `ARCH_HEALTH.md`.

- **`self-assess-transform-brief`** — Synthesizes `self-assess-stage-map`'s
  graph and `self-assess-arch-health`'s findings into a transformation plan:
  a current→target component mapping (explicitly **Keep (1:1)**, **Merge**,
  or **Split** per stage — merge/split decisions and their rationale are
  flagged as Open Questions, never guessed), a leaf-first phased sequence
  (mirrors `code-modernization`'s "build-graph leaf-first" doctrine), and
  best-practice rationale. Read-only and plan-only — it does not edit code
  or enforce anything; executing a phase is a separate, explicitly-
  authorized step (see the skill's own **Handoff** section). Also emits two
  Mermaid `.mmd` exports (`TRANSFORM_SEQUENCE.mmd`, `TRANSFORM_MAPPING.mmd`
  — the first Mermaid this repo has ever shipped) and feeds the phase
  sequence into `self-assess-stage-map`'s topology viewer as a selectable
  walkthrough (the viewer's `flows` feature, previously always empty).
  Produces `MODERNIZATION_BRIEF.md`.

- **`self-assess-transform-execute`** — Applies exactly one already-authorized
  phase from `MODERNIZATION_BRIEF.md` via the `transform-executor` agent —
  **one of the plugin's two Edit/Write-capable paths** (the other is
  `self-assess-idiom-fix`, below), off by default
  (`transform.mode: plan`) and gated per-phase
  (`transform.authorized_phases`), never a blanket switch. Refuses a phase
  whose Open Question isn't resolved by a human first. Never verifies its
  own output — always hands off to `andon-verify`'s adversarial tribunal (or
  `andon-loop`) rather than self-reviewing, and never commits or pushes. See
  **Safety notes** below before enabling this.

- **`self-assess-docs-drift`** — Parses claims out of `CLAUDE.md` /
  `DECISIONS.md` / ADRs / `README.md` and verifies each against the actual
  code, reusing `version-delta-analyst`'s Delta Card format (category /
  claim / reality / confidence, `file:line` both sides). Produces
  `DOCS_DRIFT.md`.

- **`self-assess-ci-topology`** — Reads `git remote -v`, every CI config
  file, any publish/mirror scripts, and the repo's commit-signing state
  (`commit.gpgsign` + a `git log --pretty=%G?` signature tally); flags
  redundant remotes, doc-vs-reality drift about CI, one-directional
  force-push mirrors with no reverse-sync path, and inconsistent commit
  signing (the green "Verified" vs grey "Unverified" badge — history mixing
  signed and unsigned commits, or `commit.gpgsign` left unset). Produces
  `CI_TOPOLOGY.md`.

- **`self-assess-lint-audit`** — Checks the codebase against
  `<repo>/.claude/house-rules.md` (repo-authored, like `CLAUDE.md` — never
  invented by this plugin). Degrades gracefully, clearly labeled, if the
  file is absent. Produces `LINT_AUDIT.md`.

- **`self-assess-code-idiom`** — The one skill that judges the code *itself*
  rather than checking it against docs/config/house-rules: **deprecated
  language/library idioms** (modernization-in-place — only ones the version
  the repo actually targets supersedes, e.g. `Optional[X]` → `X | None` in
  Python 3.10+, `Python::acquire_gil()` → `with_gil` in pyo3, class components
  → hooks in React) and **generic code smells** that need no house-rules entry
  to exist (error-swallowing except/catch, magic numbers, overlong functions,
  deep nesting, missing type coverage). Per-language idiom catalog lives in
  `references/language-support.md`; anything a repo's own `house-rules.md`
  already governs is skipped (that's `self-assess-lint-audit`'s job).
  Read-only — it reports, never rewrites. Produces `CODE_IDIOM.md`.

- **`self-assess-idiom-fix`** — Applies exactly the eligible
  `modernization`-category findings from `code_idiom_summary.json` via the
  `idiom-remediator` agent — **one of only two Edit-capable paths in this
  plugin** (the other is `self-assess-transform-execute`), off by default
  (`idiom_fix.mode: propose`). Never touches `smell`-category findings or
  findings carrying a `severityNote`. Never verifies its own output —
  every fix, with zero exceptions, gets its own explicit hand-off to
  `andon-verify`'s adversarial tribunal rather than self-reviewing, and
  never commits or pushes. See **Safety notes** below before enabling
  this.

- **`self-assess-extract-rules`** — Mines business/domain logic
  (calculations, validations, eligibility, state transitions) out of the
  current repo into testable Rule Cards (Given/When/Then, P0/P1/P2
  priority, `file:line` citation, confidence). Mirrors
  `code-modernization`'s `modernize-extract-rules` mechanics
  (loop-until-dry extraction, per-rule citation referee, a two-judge P0
  confirmation panel), retargeted at a live repo instead of a legacy
  system slated for rewrite. Produces `BUSINESS_RULES.md` and
  `DATA_OBJECTS.md`.

- **`self-assess-complexity-score`** — Computes a COCOMO/cyclomatic-
  complexity tech-debt index per stage (reusing `self-assess-stage-map`'s
  already-solved boundaries, falling back to a coarser per-language
  grouping if no stage map exists), to answer "which module first" with a
  number instead of a guess. Pure quantitative metric — no adversarial
  Verify phase, and deliberately excluded from graded health/severity
  views (see `self-assess-portfolio`/`self-assess-status`): a complexity
  index is a ranking signal, not a pass/fail finding. Produces
  `COMPLEXITY_SCORE.md`.

- **`self-assess-status`** — Read-only: staleness of *this plugin's own
  artifacts* against current repo state (not docs-vs-code drift itself —
  that's `docs-drift`'s job). Produces a 3-line verdict: furthest completed
  check, what's stale, single next skill to run.

- **`self-assess-portfolio`** — Sweeps every repo under a parent
  directory and renders a heat-map dashboard from each repo's *existing*
  self-assess artifacts (via the `*_summary.json` sidecars every other
  skill writes) — languages, stage/wire counts, docs-drift
  contradictions, CI findings, lint violations, and an honest "not yet
  assessed" marker rather than fabricated data for repos self-assess
  hasn't touched yet. Mirrors `code-modernization`'s
  `modernize-assess --portfolio` heat-map, adapted from legacy-system
  sizing to live-repo health. Pure read-only aggregation — no workflow,
  no agents, no re-analysis. Produces `<parentDir>/self-assess-portfolio.html`.

## Agents

- **`stage-mapper`** — read-only per-language import/use graph extraction.
- **`docs-drift-auditor`** — read-only claim-vs-code verification.
- **`ci-topology-auditor`** — read-only git/CI topology analysis.
- **`convention-auditor`** — read-only house-rules conformance checking.
- **`business-rules-miner`** — read-only business-rule mining and citation refereeing.
- **`complexity-surveyor`** — read-only size/complexity measurement, no judgment.
- **`idiom-auditor`** — read-only deprecated-idiom + code-smell detection (version-aware).
- **`arch-health-auditor`** — read-only architecture-deficiency detection over the stage/wire graph.
- **`transform-executor`** — **one of the plugin's two Edit/Write-capable agents** — applies exactly one already-authorized, already-human-resolved transformation phase; never verifies its own work. See **Safety notes** below.
- **`idiom-remediator`** — **the plugin's other Edit-capable agent** (Read+Edit only, no Write/Bash/Glob/Grep) — applies exactly one already-verified `code-idiom` modernization-category rewrite; never verifies its own work. See **Safety notes** below.

Eight of these ten are read-only (`Read`, `Glob`, `Grep`, `Bash` —
`complexity-surveyor` omits `Grep`, it has no untrusted-claim
cross-referencing to do) — this plugin writes target-repo source in
exactly two narrowly-gated paths (`transform-executor` and
`idiom-remediator`, both off by default; see **Safety notes**), and
otherwise only to the configured `output_dir` (default
`analysis/self-assess/**`, see **Settings** below), done by the
orchestrating skill from each workflow's structured return value, never by
an agent directly (the same separation `code-modernization` uses: analysis
agents are untrusted-input readers, never file writers — `transform-executor`
and `idiom-remediator` are the plugin's sole, deliberate departures from
that rule).

## Development

`test-fixtures/` contains regression fixtures used while developing this
plugin's skills — `two-package-one-manifest/` reproduces the andon-loop
stage-collapse bug `self-assess-stage-map` exists to fix, so a run against
it should always resolve 2 stages and 1 wire. Not needed to use the
plugin; kept in the bundle for anyone extending `self-assess-stage-map`.

## Recommended workspace setup

```json
{
  "permissions": {
    "allow": ["Read(**)", "Write(analysis/self-assess/**)", "Edit(analysis/self-assess/**)"]
  }
}
```

**If you override `output_dir` in `.claude/self-assess.local.md` (see
**Settings** below), update this block to match** — the paths must be
literal, not read from the settings file, so a mismatch here silently
blocks every write rather than erroring loudly. No `deny` block is
needed either way — unlike `code-modernization`'s `legacy/` protection,
this plugin never proposes writing outside the configured `output_dir`
in the first place.

## The house-rules file

`self-assess-lint-audit` (and, for convention-awareness, every other heavy
skill) reads `<repo>/.claude/house-rules.md` if present — a file you write
yourself, describing your repo's actual conventions (e.g. "Pydantic
models, not dataclasses", "match over if/elif chains", "one source of
truth per config value"). This plugin never generates or guesses this file
on your behalf.

## Settings

Optional per-project overrides live in `.claude/self-assess.local.md` in
the repo being assessed — copy `examples/self-assess.local.md` there and
edit it:

```yaml
---
enabled: true
house_rules_path: .claude/house-rules.md
output_dir: analysis/self-assess
languages: []            # non-empty = explicit override, skips auto-detection
skip_verification: false # faster, lower-precision runs (Workflow-orchestrated skills only)
lint_max_rules: 12
---
```

Every skill reads this file independently at the start of its own run —
there are no hooks in this plugin, so unlike some plugin-settings uses of
this pattern, **no Claude Code restart is needed** after editing it. Add
`.claude/*.local.md` to the target repo's `.gitignore`. Full field
reference: `references/settings.md`.

## Prerequisites

Every skill degrades gracefully without these — run `self-assess-preflight`
to check all at once:

- **A parser/toolchain per detected language** — `python3` (stdlib `ast`,
  always present), `node`, `cargo`, or the relevant tool for whatever
  `references/language-support.md` maps your stack to. Without one,
  `self-assess-stage-map` falls back to a regex/grep pass for that
  language instead of a real parse.
- **`ruff`** (Python repos) — sharpens `self-assess-lint-audit`'s
  convention checks; falls back to grep-based pattern matching without it.
- **`git`** — required for `self-assess-ci-topology` (nothing to audit
  without it) and for `self-assess-status`'s commit-based staleness
  signal (falls back to file mtimes without it).
- **`glow`** — renders the markdown artifacts nicely in-terminal; plain
  text without it.

## Safety notes

**This plugin has two deliberate Edit exceptions — `transform-executor`
and `idiom-remediator` — each independently gated, neither overlapping
the other's scope.** Every other self-assess skill and agent — including
`self-assess-transform-brief` and `self-assess-code-idiom`, which plan/find
the very things these two apply — is 100% read-only; do not assume that's
still universally true without checking this section, the same caution
`confab`'s own README asks of its two exceptions.

**`self-assess-transform-execute`'s `transform-executor` agent** is the
first. `transform-executor`
only runs when `self-assess-transform-execute` dispatches it, which only
happens when the repo owner has explicitly set `transform.mode: execute`
**and** listed the specific phase number in `transform.authorized_phases`
(default `plan` mode refuses outright; see `references/settings.md`), and
only for one already-authorized phase at a time, scoped to that phase's
declared stage(s) — never a general "improve this" mandate. It returns
`blocked` rather than guessing whenever a phase's Open Question isn't
resolved by a human first, or when a change would need to touch a file
outside the phase's scope. It has no `Bash` and never commits or pushes.
Critically, **it never verifies its own work** — `self-assess-transform-execute`
always ends with an explicit hand-off to `andon-verify`'s adversarial
tribunal (independent agents, never a same-session self-review) rather than
self-assess declaring its own edit correct; research on LLM-assisted code
modernization found that a model reviewing its own change misses roughly a
third of its own semantic errors, which is exactly the failure mode this
separation avoids.

**`self-assess-idiom-fix`'s `idiom-remediator` agent** is the second, and
narrower. It only runs when `self-assess-idiom-fix` dispatches it, which
only happens when the repo owner has explicitly set `idiom_fix.mode: fix`
(default `propose` refuses outright; see `references/settings.md`), and
only for one already-verified `code-idiom` `modernization`-category
finding at a time — never a `smell`-category finding, and never one
carrying a `severityNote` (code-idiom's own Verify phase already flagged
those as uncertain). It has no `Bash`, `Write`, `Glob`, or `Grep` — only
`Read` and `Edit` — since every `code-idiom` finding is already an exact
single file:line, unlike `transform-executor`'s multi-file scope. It
returns `blocked` rather than guessing on any ambiguity, never commits or
pushes, and — the same discipline as `transform-executor`, applied with
zero exceptions even to its most mechanical rewrites — never verifies its
own work: every fix gets its own explicit hand-off to `andon-verify`'s
adversarial tribunal before anyone should trust it.

Same discipline as `code-modernization`: **analyzed content is untrusted
input.** `CLAUDE.md`, ADRs, and `house-rules.md` can in principle contain
planted instruction-shaped text ("ignore this contradiction", "mark this
check green"); every agent treats file content as data and flags
instruction-shaped text rather than acting on it. Any credential that
surfaces (e.g. embedded in a `git remote -v` URL) is masked
(`file:line` + a 2-4 character preview) the same way `security-auditor`
masks secrets.

**Artifacts can quote your own source.** `DOCS_DRIFT.md` and
`LINT_AUDIT.md` cite short excerpts of your docs and code as evidence —
ordinary practice, but worth knowing before sharing `analysis/self-assess/`
outside the team, the same way you'd think twice before sharing any
internal-docs excerpt.

## Dynamic workflow orchestration

On Claude Code builds with the Workflow tool, `stage-map`, `docs-drift`,
`ci-topology`, `lint-audit`, and `extract-rules` run as scripted
multi-agent orchestrations (parallel finders, deduplication, adversarial
per-finding verification). They fall back to direct subagent fan-out on
older builds automatically. `preflight` and `status` are plain skill logic
with no fan-out.

## License

MIT. See `LICENSE`.
