# nacharbeit rubric

The fixed rule set nacharbeit grades a Claude Code plugin against: every skill, agent,
command, workflow prompt and reference file, plus its hooks, scripts, report viewers,
manifest, README, CHANGELOG and the repo-level developer docs that wire it in. **This
file is an input to the review, never an output of it.** Its SHA-256 rides in the
workflow `args` as `rubricHash`; every finding cites one `rule_id` from the tables below,
and a rerun with an edited rubric cannot hit the resume cache.

## Contents

- [Sources and precedence](#sources-and-precedence), [Severity](#severity), [Fix tier](#fix-tier)
- [M — mechanical rules for prompt-bearing files](#m-mechanical-rules-nacharbeit-lint-py)
- [Q — judgement rules for prompt-bearing files](#q-judgement-rules-finders-and-verifiers)
- [H — hooks](#h-hooks), [S — scripts](#s-scripts), [A — assets and viewers](#a-assets-and-viewers)
- [P — manifest, README, CHANGELOG](#p-manifest-readme-changelog), [D — repo-level developer docs](#d-repo-level-developer-docs)
- [Settled contradictions (F1–F7)](#settled-contradictions-f1-f7), [Known mis-flags](#known-mis-flags-the-finders-must-avoid)

Two rule kinds, in six families:

- **Mechanical** (`M-* H-* S-* A-* P-* D-*`) — checked by `scripts/nacharbeit_lint.py` with
  regex, a YAML parser, a JSON parser and Python's `ast`. No model in the loop. Model
  finders are told these ids are out of scope.
- **Judgement** (`Q-* HQ-* SQ-* AQ-* PQ-* DQ-*`) — checked by the sonnet finders, refuted by
  sonnet verifiers, synthesized by opus. A judgement finding must quote ≥20 verbatim
  characters from the file.

## Sources and precedence

Where sources disagree, **official Anthropic documentation wins**:

1. [Claude Code skills](https://code.claude.com/docs/en/skills)
2. [Claude Code subagents](https://code.claude.com/docs/en/sub-agents)
3. [Claude Code hooks](https://code.claude.com/docs/en/hooks)
4. [Claude Code plugins reference](https://code.claude.com/docs/en/plugins-reference)
5. [Agent Skills best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices)

Third-party rules fill gaps only: the installed `plugin-dev` and `skill-creator` plugins
(Anthropic-authored but not normative), `obra/superpowers` `writing-skills`, and the
werkstoff workshop's own `docs/plugin-authoring/references/craft-standards.md`,
`report-viewer-standard.md` and `docs/orchestration/references/hazards.md`. The seven
contradictions between those sources are settled in the last section.

## Severity

| severity | meaning |
|---|---|
| `blocker` | the component will not load, will never trigger, or violates a hard cap the runtime enforces |
| `major` | the component triggers or runs wrong in a way a user would notice |
| `minor` | measurably worse than the recommendation; fix is local |
| `nit` | style; only worth fixing when touching the file anyway |

## Fix tier

Every finding names the cheapest model that can apply its fix without judgement it lacks:
`haiku` (trim, delete, add TOC, path fix), `sonnet` (rewrite a description, add a negative
trigger, restructure steps, add an output example), `opus` (merge or rescope components,
redesign step order), `human` (changes a plugin's contract or pipeline order).

## M — mechanical rules (`nacharbeit_lint.py`)

### Frontmatter and description

| id | rule | applies to | severity | source |
|---|---|---|---|---|
| `M-FM-PARSE` | Frontmatter starts at line 1 with `---`, parses as YAML, is a mapping with a non-empty `description` (and `name` for agents). | skill, agent, command | blocker | code.claude.com/skills "YAML frontmatter must start at line 1"; sub-agents "A file without name or description is skipped" |
| `M-DESC-LEN` | `description` ≤ 1024 characters. | skill, agent | major | platform best-practices "Maximum 1,024 characters" |
| `M-DESC-XML` | `description` contains no XML-style tags such as `<example>`. | skill, agent | major | platform best-practices "Cannot contain XML tags" |
| `M-DESC-PERSON` | `description` is third person: no "I can", "I will", "You can use this", "you should". | skill, agent | minor | platform best-practices "Always write in third person" |
| `M-DESC-VAGUE` | `description` is not a generic capability claim ("Helps with…", "Processes data", "Does stuff"). | skill, agent, command | major | platform best-practices "Avoid vague descriptions" |
| `M-DESC-WHENONLY` | Skill `description` does not open with the when-only template `This skill should be used when/after/…` — it must lead with what the skill does. | skill | minor | F1 decision below; code.claude.com/skills "Put the key use case first" |
| `M-NAME-FORMAT` | `name` ≤ 64 chars, lowercase letters, digits, hyphens only, no `anthropic`/`claude`, equal to the skill directory or agent file stem. | skill, agent | major | platform best-practices frontmatter note |

### Body, references, and wiring

| id | rule | applies to | severity | source |
|---|---|---|---|---|
| `M-BODY-LINES` | SKILL.md body (after frontmatter) < 500 lines. | skill | minor | code.claude.com/skills "Keep SKILL.md under 500 lines" |
| `M-REF-TOC` | A reference file > 100 lines has a table of contents (a `Contents`/`Table of contents` heading or a link list) within its first 40 lines. | reference | minor | platform best-practices "reference files longer than 100 lines, include a table of contents" |
| `M-REF-DEPTH` | A reference file does not link to another reference file (references stay one level deep from SKILL.md). | reference | minor | platform best-practices "Keep references one level deep" |
| `M-REF-UNWIRED` | Every file under a skill's `references/` is linked or named from that skill's SKILL.md. | skill | minor | code.claude.com/skills "Reference supporting files from SKILL.md so Claude knows what each file contains and when to load it" |
| `M-LINK-BROKEN` | Every relative markdown link or backticked relative path under the plugin resolves to an existing file. | all | major | craft-standards "wiring references"; plugin-validator |
| `M-DUP-CONTENT` | No two prompt-bearing files anywhere under `plugins/` are byte-identical (a fact lives in one place). | all | minor | craft-standards "no duplication"; plugin-dev skill-development |
| `M-SKILL-VOICE` | SKILL.md body avoids second-person address ("You should", "You need to", "You can"); it uses imperative or infinitive form. | skill | nit | plugin-dev skill-development "imperative/infinitive form" |

### Agents

| id | rule | applies to | severity | source |
|---|---|---|---|---|
| `M-AGENT-VOICE` | Agent body does not speak in first person ("I will", "I am going to"). | agent | nit | plugin-dev agent-development; sub-agents "Be explicit about behavior" |
| `M-AGENT-MODEL` | Agent `model`, if present, is one of `inherit`, `sonnet`, `opus`, `haiku`, `fable`, or a full model id. | agent | major | sub-agents `model` field |
| `M-AGENT-TOOLS-SHAPE` | Agent `tools`, if present, is a comma-separated string of known tool names (not a YAML list, not `*`). | agent | minor | sub-agents `tools` allowlist syntax; CLAUDE.md gotcha on tool-declaration formats |
| `M-AGENT-TOOLS-VERBS` | An agent whose body instructs it to edit, write, create, or modify files declares `Edit` or `Write`; an agent whose body says it is read-only does not declare them. | agent | major | sub-agents "Read-only subagents: use `tools: Read, Grep, Glob`" |
| `M-VERSION-FIELD` | Frontmatter carries no `version:` key (not a documented field; nothing maintains it). | skill, agent | nit | F4 decision below; craft-standards |

### Commands, paths, and secrets

| id | rule | applies to | severity | source |
|---|---|---|---|---|
| `M-CMD-ARGHINT` | A command body that uses `$ARGUMENTS`, `$1`…`$9` declares `argument-hint`. | command | minor | plugin-dev command-development |
| `M-CMD-DESC-LEN` | Command `description` ≤ 150 chars (it renders in `/help`). | command | nit | plugin-dev command-development "≤~60 chars" relaxed |
| `M-TIME-SENSITIVE` | Body contains no dated instructions ("before &lt;month year&gt;", "as of &lt;year&gt;", "until Q3 &lt;year&gt;"). | all | minor | platform best-practices "Avoid time-sensitive information" |
| `M-WIN-PATHS` | No backslash file paths. | all | nit | platform best-practices "Avoid Windows-style paths" |
| `M-BASH-WILDCARD` | `allowed-tools` never grants `Bash(*)`, `Bash`, or `*` unscoped. | skill, command | minor | plugin-dev command-development "scope Bash" |
| `M-SECRETS` | No credential-shaped literals (`sk-…`, `ghp_…`, `AKIA…`, `password: "…"`). | all | blocker | plugin-validator |

## Q — judgement rules (finders and verifiers)

Angles map to the user's review axes: `meaning`, `contract`, `clarity`, `step-logic`,
`procedure`, `cannibalization`, `other`.

### Meaning and contract

| id | angle | rule | severity | source |
|---|---|---|---|---|
| `Q-MEANING-PROMISE` | meaning | The body delivers what the description promises, and promises nothing the body does not do. | major | platform best-practices "description … the rest of SKILL.md provides the implementation details" |
| `Q-MEANING-CONTRACT` | contract | A component that produces an artifact states its output contract (where it writes, what shape) in one place the reader can find. | major | craft-standards; output-shape-findings |
| `Q-MEANING-ASSUMED` | meaning | No hidden precondition: every input the body relies on (a file, a prior skill's artifact, a setting) is named as required, with what happens when it is absent. | major | CLAUDE.md "never infer a missing gating value" |

### Clarity

| id | angle | rule | severity | source |
|---|---|---|---|---|
| `Q-CLARITY-CONCISE` | clarity | No paragraph explains what Claude already knows; every paragraph justifies its recurring token cost. | minor | platform best-practices "Concise is key"; code.claude.com/skills "every line is a recurring token cost" |
| `Q-CLARITY-TERMS` | clarity | One term per concept throughout the file (not `finding`/`issue`/`violation` for the same thing). | minor | platform best-practices "Use consistent terminology" |
| `Q-CLARITY-OPTIONS` | clarity | One default plus a named escape hatch, not a menu of approaches. | minor | platform best-practices "Avoid offering too many options" |
| `Q-CLARITY-EXAMPLE` | clarity | Where output format matters, at least one concrete, complete example exists; placeholder-only templates do not count when the content is non-obvious. | minor | platform best-practices "Examples pattern"; output-shape-findings |
| `Q-CLARITY-AMBIG` | clarity | No sentence a careful reader could execute two different ways (undefined pronoun referents, "it", "this", "the file" with several candidates). | major | code.claude.com/sub-agents "Be explicit about behavior" |

### Step logic

| id | angle | rule | severity | source |
|---|---|---|---|---|
| `Q-STEPS-NUMBERED` | step-logic | Multi-step work is numbered, in execution order, ideally with a copyable checklist. | minor | platform best-practices "Use workflows for complex tasks" |
| `Q-STEPS-INPUTS` | step-logic | Every step consumes only artifacts an earlier step or a named input produced; no forward reference. | major | platform best-practices workflow pattern |
| `Q-STEPS-GATE` | step-logic | A step that can fail names its gate and where to return ("Only proceed when…"; "If X fails, return to step N"). | major | platform best-practices "Implement feedback loops" |
| `Q-STEPS-TERMINATION` | step-logic | Every loop or retry names its stop condition and its escalation path. | major | confab agentic-reliability categories; superpowers writing-skills |
| `Q-STEPS-PREDICATE` | step-logic | Branches key off an observable predicate, not an unconditional rule plus exemption clauses ("unless it matters"). | minor | superpowers writing-skills "observable conditional" |

### Procedure

| id | angle | rule | severity | source |
|---|---|---|---|---|
| `Q-PROC-WHATWHEN` | procedure | Description states both what the component does and when to use it, with key terms a router would match; not overfit to a literal query list. | major | platform best-practices "Writing effective descriptions" |
| `Q-PROC-FREEDOM` | procedure | Specificity matches fragility: exact commands for fragile sequences, prose direction for open-ended judgement. | minor | platform best-practices "Set appropriate degrees of freedom" |
| `Q-PROC-TOOLS-ROLE` | procedure | Agent tool grant is the minimum its stated role needs; `model` (if set) matches task difficulty (haiku read-only research, sonnet balanced, opus complex reasoning). | major | sub-agents "Model selection" and "Tool access" |
| `Q-PROC-OUTPUT-SHOWN` | procedure | A component producing a structured artifact shows one fenced instance of the shape, including the empty branch, rather than naming fields in prose. | minor | output-shape-findings §4; platform best-practices "Template pattern" |
| `Q-PROC-DISCLOSURE` | procedure | Content sits at the right level: always-loaded description is short; body is the standing instruction; bulky reference goes to `references/` and is pointed at with when-to-read guidance. | minor | code.claude.com/skills "Add supporting files"; platform best-practices "Progressive disclosure" |
| `Q-PROC-CLAUDEMD-DUP` | procedure | An agent body does not restate repository CLAUDE.md rules that load automatically. | nit | sub-agents "Don't duplicate CLAUDE.md" |
| `Q-PROC-FORK-TASK` | procedure | A skill with `context: fork` contains an actionable task, not only guidelines. | major | code.claude.com/skills "Avoid forked skills without task instructions" |

### Cannibalization

| id | angle | rule | severity | source |
|---|---|---|---|---|
| `Q-CANN-NEGATIVE` | cannibalization | Where a sibling component covers an adjacent job, the description says when *not* to use this one and names the sibling. | major | plugin-dev agent-development "Do not invoke when…" |
| `Q-CANN-OVERLAP` | cannibalization | Two components do not claim the same job for the same trigger unless one names the other as an intended handoff. Judged from the routing simulation, not from prose alone. | major | platform best-practices "Claude uses it to choose the right Skill from potentially 100+" |
| `Q-CANN-INTERNAL` | cannibalization | Within one plugin, skills have distinct triggers a router can separate. | major | plugin-dev component-patterns "distinct, non-overlapping roles" |

### Other

| id | angle | rule | severity | source |
|---|---|---|---|---|
| `Q-OTHER-RIGIDITY` | other | Guidance form matches failure type: prohibitions and red-flag tables for rule-skipping, positive recipes for wrong-shaped output. Capitalisation density alone is never a finding. | nit | F7 decision below; superpowers writing-skills |
| `Q-OTHER-STATEFUL` | other | Any stateful field (status marker, version, amendments log) has something that keeps it current, or is removed. | minor | craft-standards "structure implies a maintainer" |
| `Q-OTHER-NARRATIVE` | other | A skill or reference is a reusable instruction, not a narrative of one past session. | minor | superpowers writing-skills |
| `Q-OTHER-INJECTION` | other | The prompt contains no instruction-shaped text aimed at a reader model that the author did not intend (report, do not act). | major | canonize.js `UNTRUSTED` discipline |
| `Q-OTHER-SCRIPT-INTENT` | other | Every bundled script reference says whether to run it or read it, and names its required packages. | minor | platform best-practices "Make execution intent clear" |

## H — hooks

Applies to `hooks/hooks.json` (kind `hooks`) and every script it declares (kind
`hookscript`). The contract is Claude Code's PreToolUse protocol as
`plugins/takt/hooks/takt_guard.py` states it: deny = exit 2 + reason on stderr + stdout
JSON `{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
"permissionDecisionReason": "…"}}`; omitting `hookEventName`, or using `systemMessage`
instead of `permissionDecisionReason`, makes the runtime silently ignore the deny.

### Mechanical

| id | rule | applies to | severity | source |
|---|---|---|---|---|
| `H-JSON-PARSE` | `hooks.json` parses; `hooks` maps an event name to a list of `{matcher, hooks[]}`; ≥1 event is registered. | hooks | blocker | hooks docs (hooks.json shape); `tools/surface-index/build_surface_index.py` raises on the same |
| `H-TYPE-COMMAND` | Every handler is `type: "command"`. | hooks | major | hazards.md; `verify-hooks-deny.py` ("declares type=prompt — not enforcement") |
| `H-CMD-PLUGIN-ROOT` | Each command locates its script through `${CLAUDE_PLUGIN_ROOT}` and hard-codes no absolute path. | hooks | major | plugins-reference (`${CLAUDE_PLUGIN_ROOT}`) |
| `H-SCRIPT-EXISTS` | The script a command names exists under the plugin. | hooks | blocker | `verify-hooks-deny.py` failure mode `missing` |
| `H-TIMEOUT` | Each command handler sets an integer `timeout`. | hooks | minor | hooks docs `timeout` |
| `H-MATCHER-KNOWN` | `matcher` is `\|`-joined documented tool names (or empty / `*`). | hooks | minor | hooks docs (a matcher that matches nothing is a hook that never runs) |
| `H-MATCHER-MULTIEDIT` | A matcher naming `Edit` or `Write` also names `MultiEdit`. | hooks | nit | hazards.md ("andon's matcher does not list MultiEdit") |
| `H-INERT-STATED` | `hooks.json`'s `description` states when the hook is inert. | hooks | nit | hazards.md cards ("Inert unless") |
| `H-DENY-SHAPE` | A script that emits `permissionDecision` also emits `hookEventName`; a script using `systemMessage` without `permissionDecisionReason` fails; a script that never emits a decision fails. | hookscript | major | hooks docs (PreToolUse decision control); CLAUDE.md silent-defect row |
| `H-EXIT-2` | The deny path exits 2 (`sys.exit(2)`, `return 2` through `sys.exit(main())`, or a `DENY`/`BLOCK` constant equal to 2). | hookscript | major | hooks docs ("exit code 2 = blocking error") |
| `H-ESCAPE-HATCH` | The script reads a `<NAME>_DISABLE_GUARD` env var and names it again in a deny reason. | hookscript | minor | hazards.md ("escape hatch named in the hook's own deny message") |
| `H-FAIL-CLOSED` | The last broad `except` handler calls `deny(…)`, not `allow()`/`exit(0)` (AST proxy; documented). | hookscript | minor | hazards.md "All fail closed"; takt docstring |
| `H-MULTI-PATH` | An edit-gating script reads `edits[].file_path` and `file_paths` besides `file_path`. | hookscript | minor | `takt_guard.py::edit_targets`; `test/plugins/verify-takt-payload-shapes.py` |
| `H-TEST-EXISTS` | `test_<stem>.py` exists beside the hook script (or anywhere under the plugin). | hookscript | minor | CLAUDE.md "verify the instrument"; lehre/andon/self-assess convention |

### Judgement

| id | angle | rule | severity | source |
|---|---|---|---|---|
| `HQ-LOCK-SCOPE` | contract | A guard that arbitrates edits gates on a per-dispatch lock naming the files it may touch, never on repo-level state (the payload carries no field saying whose edit it is). | major | hazards.md "Why a hook cannot tell whose edit it is" |
| `HQ-EMPTY-SET-DENY` | step-logic | When a gated tool's target set cannot be determined, the script denies. | major | takt docstring |
| `HQ-DENY-NOT-RECIPE` | other | The denial text does not tell the caller how to forge the state that would satisfy the gate. | major | lehre Gate 0 comment; takt `ESCAPE_HATCH` wording |
| `HQ-INERT-MATCHES` | meaning | The inert condition stated in `hooks.json` and the README is the marker the script actually tests. | major | hazards.md cards |
| `HQ-README-HOOK` | procedure | The README documents the matcher, the inert condition, the escape hatch and how to test the hook. | minor | `plugins/takt/README.md` "## Hooks", "## Testing" |

## S — scripts

Applies to `scripts/**/*.{py,sh,js}` and `hooks/*.py` (kinds `script` and `hookscript`),
skipping `fixtures/` and `testdata/`. `S-JS-SYNTAX` also covers `workflows/*.js`.

### Mechanical

| id | rule | applies to | severity | source |
|---|---|---|---|---|
| `S-PY-COMPILE` | `ast.parse` succeeds. | script (.py) | blocker | CLAUDE.md verification list |
| `S-JS-SYNTAX` | `node --check` passes; when `node` is absent the rule is listed under `skipped`, never silently passed. | script (.js), workflow | blocker | `scripts/ci/check-js-syntax.sh` |
| `S-SHEBANG` | An entry-point script starts with `#!/usr/bin/env python3` (or bash). | script | nit | repo convention |
| `S-DOCSTRING-USAGE` | An entry-point `.py` has a module docstring stating its usage, or an argparse `--help`; test files are exempt. | script | minor | platform best-practices "Make execution intent clear" |
| `S-ARGPARSE` | A script reading `sys.argv` imports `argparse`. | script (.py) | minor | same; `--help` must exist |
| `S-SILENT-REGEX` | Where a regex is used, no `\b!==`, `\b===`, `[^.]{0,N≥50}`, or (in shell) `[^\n]`. | script, workflow | major | CLAUDE.md silent-defect table; `test/plugins/lint-oracles.sh` |
| `S-EXCEPT-SWALLOW` | No bare or `Exception` handler whose body is only `pass`. | script (.py) | major | CLAUDE.md "looks correct and silently does nothing" |
| `S-SHELL-TRUE` | No `subprocess` call with `shell=True` (AST). | script (.py) | minor | plugin-validator |
| `S-REFERENCED` | Every non-test script is named by a skill, agent, command, README, hooks.json or an importing sibling script. | script | minor | best-practices "reference supporting files"; `audit_reachability.py` class `unreferenced` |

### Judgement

| id | angle | rule | severity | source |
|---|---|---|---|---|
| `SQ-INTENT` | procedure | The docstring states purpose, inputs and outputs; the caller says whether to run or read it. | minor | script-side twin of `Q-OTHER-SCRIPT-INTENT` |
| `SQ-FAIL-LOUD` | step-logic | A missing or unreadable input exits non-zero and says so; it never reports "nothing found". | major | CLAUDE.md "a guard predicated on its own input existing is not a guard" |
| `SQ-STALE-OUTPUT` | contract | A failed run cannot leave a previous output looking fresh (atomic write, or a FAILED marker). | major | CLAUDE.md "a failed run leaves the previous output in place" |
| `SQ-SELF-ASSERT` | other | A checker ships a calibration that can make it go red. | major | CLAUDE.md "verify the instrument" |

## A — assets and viewers

Applies to `assets/*-viewer.html` (kind `viewer`), its screenshot, and the README
citation. The six rules the CI checker already decides delegate to
`scripts/check_viewer_conformance.py`'s `check()` (vendored from `scripts/ci/`); nothing in
it is reimplemented. The standard is `docs/plugin-authoring/references/report-viewer-standard.md`.

### Mechanical

| id | rule | applies to | severity | source |
|---|---|---|---|---|
| `A-R1-VERDICT` | A static element with `class="verdict"` states the finding in words. | viewer | major | standard R1 → checker code `R1` |
| `A-R4-LEGEND` | A static legend or note element, visible without interaction. | viewer | major | standard R4 → `R4` |
| `A-S1-HEIGHT` | No hard-coded `61px` header height. | viewer | minor | standard S1 → `S1` |
| `A-S2-HEAD` | CSP `default-src 'none'`, the canonical tokens marker, `<title>` = `<plugin> — <noun>`, a static `<h1>` equal to it and not overwritten. | viewer | major | standard S2 → `S2` |
| `A-C1-SCREENSHOT` | `<viewer>-screenshot.jpg` exists, 1600 px wide, and parses. | viewer | minor | standard C1 → `C1` |
| `A-C2-DEMO-DATA` | The README cites committed demo data under `scripts/fixtures/` or `scripts/testdata/`. | viewer | minor | standard C2 → `C2` |
| `A-S3-INNERHTML` | No `innerHTML=`/`outerHTML=`/`insertAdjacentHTML(` fed anything but a constant literal. | viewer | major | standard S3 (second barrier) |
| `A-S4-FAIL-VISIBLE` | The script contains a visible-failure branch that tells the reader to re-run or regenerate (documented proxy). | viewer | minor | standard S4 |
| `A-NO-CDN` | No `<script src=` / `<link href=` to the network. | viewer | major | standard S2 CSP rationale; `tools/d3-subset` |
| `A-TOKENS-PRESENT` | A plugin with a viewer ships `assets/tokens.css`. | viewer | minor | standard "What is mechanically checked" |
| `A-BUILDER-EXISTS` | A `scripts/*.py` names the viewer or injects the `__DESIGN_TOKENS__` marker. | viewer | minor | standard (builder + template pairing) |
| `A-C4-ALT` | The README's screenshot alt text is ≥10 characters and not the plugin name. | readme | nit | standard C4 |
| `A-VIEWER-REQUIRED` | The plugin ships at least one `assets/*-viewer.html`. Keyed on the manifest, because every other `A-*` rule grades a viewer that exists and so can never report one that does not. | manifest | major | CLAUDE.md "Every plugin ships an HTML report viewer" |

### Judgement

| id | angle | rule | severity | source |
|---|---|---|---|---|
| `AQ-R2-ONCE` | clarity | No number is printed twice. | minor | standard R2 |
| `AQ-R3-ACTIONABLE` | clarity | An actionable number does not look inert. | minor | standard R3 |
| `AQ-R5-HEIGHT` | procedure | Height derives from content, not a fixed viewport. | minor | standard R5 |
| `AQ-C3-SHOWS-FAILURE` | meaning | The demo data shows the failure the plugin exists for. | major | standard C3 |

## P — manifest, README, CHANGELOG

Applies to `.claude-plugin/plugin.json` (kind `manifest`), `README.md` (kind `readme`),
`CHANGELOG.md` (kind `changelog`) and the plugin's `skills/` and `references/` layout.
`P-MARKETPLACE-MEMBER` runs only with `--marketplace` and is fix-tier **human**: the
marketplace entry lives outside the plugin.

### Mechanical

| id | rule | applies to | severity | source |
|---|---|---|---|---|
| `P-MANIFEST-PARSE` | `plugin.json` exists and parses to an object with non-empty `name`, `version`, `description`. | manifest | blocker | plugins-reference; `claude plugin validate --strict` |
| `P-MANIFEST-NAME-DIR` | `name` equals the plugin directory name. | manifest | major | plugins-reference |
| `P-MANIFEST-SEMVER` | `version` is `x.y.z`. | manifest | major | rrt `package_json` version target |
| `P-AUTHOR-PRESENT` | `author.name` is non-empty and not a placeholder. | manifest | major | `test/plugins/lint-plugin-authors.py` |
| `P-MARKETPLACE-MEMBER` | The marketplace entry exists; `author.name` and `description` equal the manifest's; `source` points at `./plugins/<name>`. | manifest | major | lint-plugin-authors; `.rrt.toml` field_targets |
| `P-MANIFEST-KEYWORDS` | `keywords` is a non-empty list. | manifest | nit | takt convention |
| `P-MANIFEST-LICENSE` | `license` is present. | manifest | nit | takt convention |
| `P-README-H1` | `README.md` exists and its first heading is `# <name>`. | readme | minor | lehre/takt |
| `P-README-THESIS` | A bold one-line thesis sits directly under the H1. | readme | nit | lehre/takt |
| `P-README-WHY-NOT` | `## Why this exists` and `## What it is not` are present. | readme | minor | lehre |
| `P-README-INSTALL` | An `## Install` section carries `/plugin install <name>@…` or a `--plugin-dir` line. | readme | minor | lehre/takt |
| `P-README-PROMPTS-BLOCK` | (with `--readme-markers`) the rrt `example-prompts-intro` marker pair is present. | readme | minor | `.rrt.toml` shared_blocks; `rrt docs inject --check` |
| `P-README-PROMPT-TRIPLE` | Under `## Example Prompts`, every `#####` label is followed by a ````prompt fence, and ≥1 exists (mirrors `build_prompt_index.py`'s scan). | readme | minor | `tools/prompt-index/build_prompt_index.py` |
| `P-README-VERIFY` | A `## Verifying …` or `## Testing` section exists. | readme | nit | lehre/takt |
| `P-README-ESCAPE-HATCH` | A plugin with a hook names its `_DISABLE_GUARD` variable in the README. | readme | minor | hazards.md |
| `P-README-SCREENSHOT` | A plugin with a viewer embeds its screenshot in the README. | readme | minor | standard C2 |
| `P-CHANGELOG-UNRELEASED` | `CHANGELOG.md` exists with a `## [Unreleased]` section. | changelog | minor | `.rrt.toml` changelog_file |
| `P-SKILL-DIR-HAS-FILE` | Every `skills/*/` directory contains `SKILL.md`. | manifest | major | code.claude.com/skills (a directory without one is silently ignored) |
| `P-REF-REACHABLE` | Every plugin-level `references/*.md` is named by a skill, agent, command or the README. | manifest | minor | plugin-level twin of `M-REF-UNWIRED` |

### Judgement

| id | angle | rule | severity | source |
|---|---|---|---|---|
| `PQ-THESIS` | meaning | The README thesis and the manifest description promise the same job. | major | plugin-level `Q-MEANING-PROMISE` |
| `PQ-NOT-SECTION` | cannibalization | "What it is not" names the sibling plugins with adjacent jobs. | major | lehre README; routing.md |
| `PQ-WRITE-SURFACE` | contract | The description states the write surface: read-only, a scoped output dir, or the named Edit exceptions. | major | every werkstoff marketplace entry |
| `PQ-PROMPTS-ROUTE` | cannibalization | The example prompts route to this plugin's own skills (cross-checked with the routing simulation). | major | `docs/prompt-index.md` known answers |
| `PQ-NARRATIVE` | other | The README is a reference, not a log of one session. | minor | superpowers writing-skills |

## D — repo-level developer docs

Applies only with `--docs-root` (kind `docs`, one unit per plugin). These are the places a
docs-bearing repo like werkstoff has to wire a plugin into; each has drifted at least
once (lehre shipped without a root-README bullet or a hazards card).

### Mechanical

| id | rule | applies to | severity | source |
|---|---|---|---|---|
| `D-DOCS-STUB` | `docs/plugins/<name>.md` exists and `@include`s the plugin README. | docs | major | `test/docs/docs_ux_audit.py` |
| `D-SIDEBAR-ENTRY` | `docs/.vitepress/config.mjs` links `/plugins/<name>`. | docs | major | lehre commit e3d4f53 |
| `D-SIDEBAR-REFS` | Every `docs/plugins/references/*.md` stub that includes one of the plugin's references is linked from the sidebar. | docs | minor | lehre's ruleset-schema stub |
| `D-GRID-ENTRY` | `PluginGrid.vue` carries a card for the plugin. | docs | minor | the component's own "hand-kept" comment |
| `D-COUNT-PROSE` | The "N plugins" count in headings, taglines and the CLAUDE.md Layout line equals the plugins on disk (reported once). | docs | minor | `docs/index.md`, `docs/plugins/index.md`, CLAUDE.md |
| `D-ROOT-README` | The root README links `plugins/<name>/README.md` and names the plugin. | docs | minor | root README `## Plugins` |
| `D-CLAUDE-MD-LAYOUT` | CLAUDE.md's `## Layout` list names the plugin. | docs | minor | CLAUDE.md |
| `D-ORCH-TABLES` | `docs/orchestration/README.md` mentions the plugin (so its skills are classified as orchestrators or leaves). | docs | minor | orchestration README |
| `D-HAZARDS-CARD` | A plugin with a hook has a card in `docs/orchestration/references/hazards.md`. | docs | minor | hazards.md |
| `D-CATALOG-VALID` | Every `docs/catalog/**` beat naming `<name>:<id>` resolves to a skill, agent or command of the plugin. | docs | major | `tools/catalog-validator/validate_catalog.py` |
| `D-GENERATED-FRESH` | `docs/prompt-index.md` has the plugin's section and `surface.json` carries its current version. | docs | major | the two generators; `docs.yml` diff gate |

### Judgement

| id | angle | rule | severity | source |
|---|---|---|---|---|
| `DQ-DOCS-MATCH` | meaning | Docs-site prose about the plugin matches what its skills and hooks do. | major | plugin-level `Q-MEANING-PROMISE` |
| `DQ-ROUTING-STATED` | cannibalization | `routing.md` names which sibling pipeline owns an overlapping task. | minor | routing.md "Two honest overlaps" |

## Settled contradictions (F1–F7)

| # | disagreement | decision |
|---|---|---|
| F1 | description = what + when (official, plugin-dev) vs when-only (superpowers) vs intent categories, no literal list (skill-creator) | **What + when, third person, key terms included.** When-only boilerplate is `M-DESC-WHENONLY` (minor). Summarising the workflow in the description is not penalised. Overfit literal query lists are a `Q-PROC-WHATWHEN` minor. |
| F2 | agent `<example>` transcript blocks required (validator) vs deprecated (docs) | **Neither required nor forbidden** in the body. In the `description` field they are `M-DESC-XML` (official: no XML tags) and usually also `M-DESC-LEN`. |
| F3 | five different body-length ceilings | **< 500 lines** (official). Word-count targets are advisory and produce no finding. |
| F4 | `version:` in frontmatter | Not a documented field. `M-VERSION-FIELD`, `nit`. |
| F5 | hook docs contradict themselves on prompt-hook events and `hooks.json` shape | **In scope, as `H-*` / `HQ-*`.** An enforcement hook is `type: "command"` (a prompt hook asks a model to decide, which is the model-mediated path a hook exists to replace — hazards.md); `H-TYPE-COMMAND` reports a prompt hook. The `hooks.json` shape graded is the one every command hook in the wild uses: `hooks.<event>[].{matcher, hooks[].{type, command, timeout}}`. |
| F6 | `.claude/commands/` is "legacy" | Reported **once**, as a cross-plugin `nit` against codebase-consistency's command set, not per file. |
| F7 | ALL-CAPS / rigid structure is a yellow flag vs bulletproofing toolkit | **Form follows failure type** (`Q-OTHER-RIGIDITY`). Density of MUST/NEVER is never a finding on its own. |

## Known mis-flags the finders must avoid

- "This skill should be used when…" **is** third person. The defect is when-only
  (`M-DESC-WHENONLY`), not voice.
- Workflow `.js` files contain `${…}` template interpolations inside `agent()` prompt
  strings. These are not undefined placeholders.
- `MUST`/`NEVER` density is not a finding (`F7`).
- A fenced example that is a *template* is only a finding when the content of the format
  is non-obvious (`Q-CLARITY-EXAMPLE`).
- Handoffs a description names explicitly ("hands off to `andon-verify`") are intended
  overlaps, not `Q-CANN-OVERLAP`.
