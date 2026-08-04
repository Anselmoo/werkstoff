# self-assess

Comprehensive self-assessment of live codebases: architecture, documentation drift, CI/CD
topology, conventions, code idioms, business rules, and UI/accessibility — with findings
carrying `file:line` evidence, synthesized into a prioritized, gated transformation plan, and
(only when explicitly authorized) one gated transformation phase applied to source.

## Why this exists

A codebase self-assessment is only useful if its findings are trustworthy —
a report that hallucinates a stale doc claim or an architecture violation
costs more time to fact-check than it saves. self-assess ties every finding
to `file:line` evidence read from the actual repository, keeps its CHECK
phase strictly read-only, and gates the one place it can touch source (the
FIX phase) behind explicit human authorization recorded on disk, not just a
remembered "yes" earlier in the conversation.

## Install

```
/plugin marketplace add Anselmoo/werkstoff
/plugin install self-assess@werkstoff
```

Or for local development, point Claude Code straight at the plugin directory
without registering the marketplace:

```bash
cc --plugin-dir /path/to/werkstoff/plugins/self-assess
```

<!-- rrt:auto:start:example-prompts-intro -->
## Example Prompts

Say any of these to Claude Code once the plugin is installed — they're plain-language
prompts, not exact phrasing Claude has to match. Claude routes them to the skill below
by intent.
<!-- rrt:auto:end:example-prompts-intro -->

##### Map the architecture

````prompt
"map this repo's architecture"
````

> Triggers `self-assess-stage-map` — import-graph-based stage/wire detection, not
> naive directory guessing.

Alongside the JSON stage graph, this skill renders a self-contained HTML viewer
(`build_stage_map_html.py`) that lays the real dependency graph out as a live
`d3-force` physics simulation on canvas: nodes cluster by actual connectivity
instead of directory structure, so a tight interconnected core reads as a
visible cluster and an unconnected module drifts off on its own.

![Force-directed dependency graph rendered on canvas: a gold-outlined "core" god-module node sits at the center of a tight cluster of blue stage nodes (api, ui, cache, utils, legacy), two red nodes (auth, db) forming one real mutual-dependency cycle, two purple nodes (worker, queue) forming a second cycle, and an unconnected "sandbox" node drifted into the opposite corner of the canvas with no edges to the rest of the graph at all](assets/stage-map-viewer-screenshot.jpg)

##### Run the auto-pilot

````prompt
"run the auto-pilot"
````

> Triggers `self-assess-autopilot` — full check → plan → gate → fix/validate, gated
> behind explicit settings before anything is written.

##### Check status

````prompt
"where does self-assess stand"
````

> Triggers `self-assess-status` — read-only board of what's been run and what's
> stale.

##### Sweep a portfolio

````prompt
"sweep our whole portfolio of repos"
````

> Triggers `self-assess-portfolio` — multi-repo dashboard, graded worst-signal-wins.

##### Check readiness first

````prompt
"can self-assess actually analyze this codebase?"
````

> Triggers `self-assess-preflight` — verifies language detection, tool availability,
> house-rules presence, and git/CI presence, then assigns a Ready/Ready-with-gaps/
> Not-ready verdict per downstream skill.

##### Find architecture problems

````prompt
"find god-modules or dependency cycles in this codebase"
````

> Triggers `self-assess-arch-health` — reads the stage graph from
> `self-assess-stage-map` and confirms every candidate god-module or cycle against
> actual code, not just the graph.

##### Audit git/CI setup

````prompt
"check our git remotes and CI setup for redundant mirrors"
````

> Triggers `self-assess-ci-topology` — audits remote topology and CI config for
> redundancy and mirror risk, masking every credential to a short preview.

##### Find modernization opportunities

````prompt
"find deprecated idioms and code smells in this repo"
````

> Triggers `self-assess-code-idiom` — judges idioms against the actual language
> version declared in the repo's own manifest, never a fixed list, and separates
> fixable modernization from judgment-requiring smells.

##### Score complexity per module

````prompt
"which module needs attention first? score complexity per stage"
````

> Triggers `self-assess-complexity-score` — computes a relative complexity index
> (2.94 × KSLOC^1.10) per stage, and lists unmeasured stages plainly rather than
> inventing numbers.

##### Check documentation accuracy

````prompt
"does our README still match what the code actually does?"
````

> Triggers `self-assess-docs-drift` — extracts falsifiable claims from
> CLAUDE.md/README/ADRs and verifies each one against the cited code.

##### Mine the hidden business rules

````prompt
"document the domain rules hidden in this code as testable specs"
````

> Triggers `self-assess-extract-rules` — mines calculations, validations, and
> state transitions into Given/When/Then rules, looping to convergence and
> requiring a two-judge panel to confirm any P0 rule.

##### Apply the modernization findings

````prompt
"apply the modernization findings self-assess-code-idiom found"
````

> Triggers `self-assess-idiom-fix` — applies only eligible modernization-category
> findings, gated behind `idiom_fix.mode: fix`, one remediator dispatch per
> (file, kind) cluster, then hands off to `andon-verify` unverified.

##### Check our own conventions

````prompt
"audit this code against our house rules"
````

> Triggers `self-assess-lint-audit` — extracts discrete rules from
> `.claude/house-rules.md` (or CLAUDE.md as a fallback) and verifies violations,
> capped at `lint_max_rules` dispatches.

##### Turn findings into a plan

````prompt
"synthesize all the findings into a modernization brief"
````

> Triggers `self-assess-transform-brief` — synthesizes stage-map, arch-health, and
> every other domain summary into a phased, ranked, read-only transformation plan.

##### Execute one authorized phase

````prompt
"execute phase 3 from the modernization brief"
````

> Triggers `self-assess-transform-execute` — applies exactly one human-authorized
> phase, gated behind `transform.mode: execute`, a clean tree, and every Open
> Question resolved.

##### Audit UI accessibility

````prompt
"check our components for accessibility issues and hardcoded design values"
````

> Triggers `self-assess-ui-audit` — statically audits JSX/TSX, Vue/Svelte, HTML,
> and CSS/SCSS for accessibility and design-token problems, never running or
> rendering the app.

Set `transform.mode: execute` and list authorized phase numbers, or `idiom_fix.mode:
fix`, in `.claude/self-assess.local.md` only when ready to apply a change — both
default to a plan/propose-only mode that refuses to touch source.

## Why this plugin is structured the way it is

Every skill in this plugin is a thin markdown workflow that calls into one shared Python
library (`scripts/lib/`) through a single CLI entry point (`scripts/self_assess_cli.py`) for
every rule that has to actually *refuse* something: a disabled skill, a dirty tree, an
unauthorized transform phase, a missing gating field in a persisted artifact, a write path that
escapes the plugin's output directory, a numeric threshold. The SKILL.md files describe
*workflow*; the CLI enforces *rules*. A skill that gets a non-zero exit from the CLI is
required to stop and surface the message — that is the refusal, not a suggestion the model can
talk itself out of.

```
self-assess/
├── .claude-plugin/plugin.json
├── scripts/
│   ├── self_assess_cli.py     # single entry point, one subcommand per enforced rule
│   └── lib/                   # the actual logic: settings, gates, validators, formulas, graph...
├── skills/self-assess-*/SKILL.md   # 16 skills, one per spec entry
└── agents/*.md                     # 11 agents, one per spec entry
```

## Settings: `.claude/self-assess.local.md`

All settings live in YAML frontmatter in this file, read fresh by every skill invocation via
`self_assess_cli.py get-settings`. Absence of the file is a fully valid, fully-defaulted
configuration — nothing is required to exist.

```markdown
---
enabled: true                 # global off-switch; per-skill overrides supported (see below)
output_dir: analysis/self-assess  # every artifact this plugin writes lands here
skip_verification: false      # true = label findings unverified instead of adversarially refuting
lint_max_rules: 12            # cap on self-assess-lint-audit's finder dispatch
require_clean_tree: true      # dirty-tree gate for the two write-capable skills
transform:
  mode: plan                  # "execute" required to run self-assess-transform-execute
  authorized_phases: []       # phase numbers explicitly authorized for execution
idiom_fix:
  mode: propose                # "fix" required to run self-assess-idiom-fix
extract_rules:
  maxRounds: 4                 # hard-capped at 4 in code; this can only lower it, never raise it
autopilot:
  fix_approved: false          # persisted approval gate for autopilot's FIX phase
  approved_phases: []
---
```

Per-skill overrides: nest a block under the skill's id (e.g. `self-assess-ui-audit:\n  enabled:
false`) to disable just that skill.

## Design decisions (spec was silent here)

The behavioral spec states obligations, not implementation details. Where it left a concrete
choice unstated, this is what was chosen and why:

- **`output_dir` default is `analysis/self-assess`**, matching the prior implementation's
  documented output location.
- **Settings parser is a small dependency-free YAML subset**, not PyYAML. The plugin ships zero
  third-party Python dependencies; `scripts/lib/frontmatter.py` handles flat scalars, one level
  of nested mapping, and simple scalar lists — everything every settings field in this plugin
  actually needs. It will not parse arbitrary YAML.
- **God-module fan-in threshold.** The spec says "high fan-in/fan-out" with no number. This
  plugin flags a stage once its fan-in reaches `max(3, 0.5 × other_stage_count)` — see
  `GOD_MODULE_FANIN_RATIO` / `GOD_MODULE_MIN_FANIN` in `scripts/lib/graph.py`. `arch-health-
  auditor` still confirms or refutes every mechanically-flagged candidate against actual code
  before it becomes a finding, so this threshold only decides what gets a second look, not what
  gets reported.
- **Autopilot's "gate before FIX" is a persisted flag, not a remembered conversational yes.**
  The spec says the skill "MUST ask the user to approve" — to make that mechanically checkable
  rather than trusting the model to recall it asked, approval must be recorded as
  `autopilot.fix_approved: true` (and optionally `autopilot.approved_phases`) in
  `.claude/self-assess.local.md` before `self_assess_cli.py autopilot-fix-gate` will pass.
- **Confab-installed detection is best-effort.** There is no API a plugin script can call to
  query "is plugin X installed" from inside this session. `self-assess-autopilot` checks
  whether a `confab:`-prefixed skill appears in the current session's available-skills listing;
  if it does not, it reports "confab not installed" and continues. This cannot be made fully
  mechanical without a host-level plugin registry API.
- **Portfolio report location.** `self-assess-portfolio` is the one skill whose output is not
  scoped to a single repo's `output_dir` — its `self-assess-portfolio.html` lands in the
  portfolio directory itself, since it summarizes many repos at once.
- **`self-assess-code-idiom`'s version detection** covers Python (`pyproject.toml` /
  `setup.py`), JavaScript/TypeScript (`package.json` engines.node), Go (`go.mod`), and Java
  (`pom.xml`) out of the box (`scripts/lib/version_detect.py`). A language outside this list
  gets `version: null`, in which case the skill's own instructions require flagging only idioms
  deprecated across every version the language has shipped, never a version-specific one.
- **Credential preview length** is clamped to 2–4 characters (`scripts/lib/credentials.py`),
  matching the spec's "2-4 character preview" exactly rather than picking one fixed number.
- **CI-scope claim exclusion** (`docs-drift-not-ci-specific`) is a fixed set of path/keyword
  patterns (`.github/workflows/`, `.gitlab-ci.yml`, `Jenkinsfile`, `.circleci/config.yml`,
  `azure-pipelines.yml`, plus "git remote"/"mirror script"/"pipeline config" keywords) rather
  than a judgment call each run — see `scripts/lib/scope.py`.

## How enforcement actually works (mapping rules to code)

| Rule (spec id) | Enforced by |
|---|---|
| `skill-reads-own-settings-before-running` | `settings.require_enabled()` — `check-enabled` subcommand |
| `lint-max-rules-cap` | `lint_cap.cap_rules()` — hard `DEFAULT_MAX_RULES = 12`, always returns a `skipped` list |
| `complexity-score-formula` | `formulas.complexity_index()` — `2.94 × KSLOC^1.10`, and `validators.validate_complexity_score_summary` recomputes it and rejects a mismatch |
| `language-detection-threshold` | `language_detect.detect_languages()` — `MIN_FILES_FOR_DETECTION = 3` |
| `cycle-definition-in-graph` | `graph.find_cycles()` — Tarjan SCC, `MIN_CYCLE_SIZE = 2` |
| `p0-rule-panel-confirmation` | `p0_panel.confirm_p0_rule()` plus `validators.validate_business_rules_summary` refusing any P0 rule without `panel_confirmed: true` |
| `extract-rules-loop-convergence` | `rules_loop.RuleLoopController` — hard `MAX_ROUNDS_HARD_CAP = 4`, 2 consecutive dry rounds to converge |
| `stage-graph-vs-stage-map-json` | `validators.validate_stage_graph` rejects the artifact unless `edgeCount == len(wires)` |
| `file-stage-index-partial-coverage` | `attribution.attribute()` returns `"Unattributed"` on any miss, never an error |
| `skip-verification-behavior` | `skip_verification.label_findings()` — refuses a finding missing `verified` when `skip_verification` is false |
| `credential-masking-in-output` | `credentials.mask_url()` / `mask_text()`; `validators.validate_ci_topology_summary` refuses any finding carrying `raw_remote_url` |
| `docs-drift-not-ci-specific` | `scope.exclude_ci_claims()` |
| `idiom-fix-modernization-only` | `gates.filter_eligible_idiom_findings()` |
| `transform-brief-gate-on-stage-graph` | skill-level file-existence check, degrades to a short brief |
| `transform-brief-attributes-findings-via-lookup` | `attribution.attribute()` |
| `transform-brief-work-item-ranking` | `formulas.work_item_rank()` — fixed `SEVERITY_WEIGHT` map |
| `transform-brief-confab-routing` | `transform_routing.route_confab_finding()` |
| `transform-execute-gate-transform-mode` | `gates.check_transform_mode()` / `check_phase_authorized()` |
| `transform-execute-open-question-resolution` | `gates.check_open_questions_resolved()` |
| `portfolio-grade-worst-signal-wins` | `portfolio.grade_repo()` — `Gray` branch checked first, unconditionally |
| `portfolio-cwd-git-repo-check` | `gates.check_portfolio_scope()` |
| `read-only-skills-no-mutation` | tool restrictions in each SKILL.md / agent frontmatter (`Read, Glob, Grep, Bash` only) |
| `dirty-tree-gate` | `gates.check_dirty_tree()` |
| `no-commit-or-push` | no code path in any skill or agent invokes `git commit`/`git push` |
| `ui-audit-static-only` | `validators.validate_ui_audit_summary` refuses a `contrast` finding without `heuristic: true` |
| `autopilot-gate-before-fix` | `gates.check_autopilot_fix_approved()` |
| `status-no-fabrication` | `status.build_present_artifacts()` — only includes a key when its sidecar file exists on disk |
| write-scope enforcement | `write_guard.resolve_output_path()` — rejects traversal, absolute paths, and any escape of `output_dir` before any write |

## Testing performed

Every subcommand above was exercised directly against both the passing and refusing case
(clean settings vs. a disabled skill, a valid path vs. path traversal, a 2-cycle graph vs. a
non-cycle, a single P0 judge vs. two agreeing judges, 15 extracted lint rules capped to 12,
`transform.mode: plan` refused vs. `execute` + authorized phase accepted, a dirty non-git
directory refused, `autopilot.fix_approved` defaulting to refused) — all producing the expected
exit code and message. See `scripts/self_assess_cli.py --help` for the full subcommand list.

## Skills (16)

`self-assess-preflight`, `self-assess-stage-map`, `self-assess-docs-drift`,
`self-assess-ci-topology`, `self-assess-lint-audit`, `self-assess-code-idiom`,
`self-assess-extract-rules`, `self-assess-arch-health`, `self-assess-complexity-score`,
`self-assess-ui-audit`, `self-assess-transform-brief`, `self-assess-transform-execute`,
`self-assess-idiom-fix`, `self-assess-status`, `self-assess-portfolio`,
`self-assess-autopilot`.

## Agents (11)

`stage-mapper`, `arch-health-auditor`, `ci-topology-auditor`, `docs-drift-auditor`,
`convention-auditor`, `idiom-auditor`, `business-rules-miner`, `complexity-surveyor`,
`ui-auditor`, `idiom-remediator` (write-capable), `transform-executor` (write-capable).

Every other agent is strictly read-only (`Read`, `Glob`, `Grep`, `Bash` for inspection only).

Set `transform.mode: execute` and list authorized phase numbers, or `idiom_fix.mode: fix`, in
`.claude/self-assess.local.md` only when ready to apply a change — both default to a
plan/propose-only mode that refuses to touch source.
