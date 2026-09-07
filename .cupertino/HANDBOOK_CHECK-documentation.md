# Handbook check — documentation

Checked against `.cupertino/documentation-handbook.md`'s 6 dimensions. 97 finding(s) survived independent re-verification (0 mechanical, 97 needing design judgment).

**Resolved since this report** (not re-run through the check workflow; noted by hand): all 41 `tone-and-audience` findings on agent files — every file under `plugins/*/agents/*.md` flagged by this check — are now rewritten to imperative/infinitive mood, done in two passes. First pass (20 files) covered the ones opening with second-person persona framing (`"You are <name>, a <role>..."`): `plugins/andon/agents/{andon-challenger,andon-defender}.md`, `plugins/codebase-consistency/agents/{align-executor,consistency-critic,equivalence-verifier,pattern-analyst,pattern-extractor}.md`, `plugins/confab/agents/confab-remediator.md`, `plugins/lehre/agents/violation-verifier.md`, and 11 files under `plugins/self-assess/agents/`. Second pass (21 files) covered files flagged for scattered mid-body second-person phrasing that didn't necessarily open with "You are": `plugins/andon/agents/{andon-adjudicator,andon-verifier}.md`, `plugins/cli-scaffold/agents/cli-scaffold-verifier.md`, `plugins/compass/agents/{branch-proposer,instruction-candidate,reasoning-path}.md`, `plugins/confab/agents/{agentic-reliability-auditor,assertion-auditor,contract-auditor,dependency-auditor}.md`, `plugins/cupertino/agents/{handbook-dimension-analyst,handbook-drift-auditor,handbook-remediator,handbook-verifier}.md`, and 7 files under `plugins/lehre/agents/`. Verified with a full re-grep for `you`/`your`/`yourself` across all 41 files (one legitimate exception left: a quoted hypothetical doc string inside `docs-drift-auditor.md`'s example output).

Remaining open: 38 `tone-and-audience` findings, all in `SKILL.md` files — incidental mid-sentence "you" in otherwise-imperative prose, not persona framing. A materially softer case than the agent-file findings, not yet addressed.

| Severity | Mechanical | Dimension | Location | Title |
|---|---|---|---|---|
| High | no | versioning-of-docs | `docs/plugin-benchmark-phase1-results.md:25` | Entire benchmark-results document has no commit/date pin for measured file/score counts |
| High | no | versioning-of-docs | `docs/plugin-benchmark-phase2-results.md:12` | Entire executed-chain benchmark document has no commit/date pin for measured pass/fail results |
| High | no | tone-and-audience | `plugins/andon/agents/andon-adjudicator.md:12` | Agent body written in second person ("You are...") instead of imperative mood |
| High | no | tone-and-audience | `plugins/andon/agents/andon-challenger.md:12` | Agent body written in second person ("You are...") instead of imperative mood |
| High | no | tone-and-audience | `plugins/andon/agents/andon-defender.md:12` | Agent body written in second person ("You are...") instead of imperative mood |
| High | no | tone-and-audience | `plugins/andon/agents/andon-verifier.md:13` | Agent body written in second person ("You are...") instead of imperative mood |
| High | no | tone-and-audience | `plugins/cli-scaffold/agents/cli-scaffold-verifier.md:39` | Agent body written in second person ("You are...") instead of imperative mood |
| High | no | tone-and-audience | `plugins/codebase-consistency/agents/align-executor.md:7` | Agent body written in second person ("You are...") instead of imperative mood |
| High | no | tone-and-audience | `plugins/codebase-consistency/agents/consistency-critic.md:7` | Agent body written in second person ("You are...") instead of imperative mood |
| High | no | tone-and-audience | `plugins/codebase-consistency/agents/equivalence-verifier.md:7` | Agent body written in second person ("You are...") instead of imperative mood |
| High | no | tone-and-audience | `plugins/codebase-consistency/agents/pattern-analyst.md:7` | Agent body written in second person ("You are...") instead of imperative mood |
| High | no | tone-and-audience | `plugins/codebase-consistency/agents/pattern-extractor.md:7` | Agent body written in second person ("You are...") instead of imperative mood |
| High | no | tone-and-audience | `plugins/compass/agents/branch-proposer.md:17` | Agent body written in second person ("You are...") instead of imperative mood |
| High | no | tone-and-audience | `plugins/compass/agents/instruction-candidate.md:17` | Agent body written in second person ("You are...") instead of imperative mood |
| High | no | tone-and-audience | `plugins/compass/agents/reasoning-path.md:16` | Agent body written in second person ("You are...") instead of imperative mood |
| High | no | tone-and-audience | `plugins/confab/agents/agentic-reliability-auditor.md:7` | Agent body written in second person ("You are...") instead of imperative mood |
| High | no | tone-and-audience | `plugins/confab/agents/assertion-auditor.md:7` | Agent body written in second person ("You are...") instead of imperative mood |
| High | no | tone-and-audience | `plugins/confab/agents/confab-remediator.md:7` | Agent body written in second person ("You are...") instead of imperative mood |
| High | no | tone-and-audience | `plugins/confab/agents/contract-auditor.md:7` | Agent body written in second person ("You are...") instead of imperative mood |
| High | no | tone-and-audience | `plugins/confab/agents/dependency-auditor.md:7` | Agent body written in second person ("You are...") instead of imperative mood |
| High | no | tone-and-audience | `plugins/cupertino/agents/handbook-dimension-analyst.md:9` | Agent body written in second person ("You are...") instead of imperative mood |
| High | no | tone-and-audience | `plugins/cupertino/agents/handbook-drift-auditor.md:9` | Agent body written in second person ("You are...") instead of imperative mood |
| High | no | tone-and-audience | `plugins/cupertino/agents/handbook-remediator.md:9` | Agent body written in second person ("You are...") instead of imperative mood |
| High | no | tone-and-audience | `plugins/cupertino/agents/handbook-verifier.md:9` | Agent body written in second person ("You are...") instead of imperative mood |
| High | no | api-reference-completeness | `plugins/lehre/README.md:1` | lehre README has no Skills or Agents section at all |
| High | no | tone-and-audience | `plugins/lehre/agents/conformance-remediator.md:9` | Agent body written in second person ("You are...") instead of imperative mood |
| High | no | tone-and-audience | `plugins/lehre/agents/doctrine-researcher.md:9` | Agent body written in second person ("You are...") instead of imperative mood |
| High | no | tone-and-audience | `plugins/lehre/agents/pattern-investigator.md:9` | Agent body written in second person ("You are...") instead of imperative mood |
| High | no | tone-and-audience | `plugins/lehre/agents/rule-critic.md:9` | Agent body written in second person ("You are...") instead of imperative mood |
| High | no | tone-and-audience | `plugins/lehre/agents/spec-decomposer.md:9` | Agent body written in second person ("You are...") instead of imperative mood |
| High | no | tone-and-audience | `plugins/lehre/agents/spec-fidelity-auditor.md:9` | Agent body written in second person ("You are...") instead of imperative mood |
| High | no | tone-and-audience | `plugins/lehre/agents/violation-auditor.md:9` | Agent body written in second person ("You are...") instead of imperative mood |
| High | no | tone-and-audience | `plugins/lehre/agents/violation-verifier.md:9` | Agent body written in second person ("You are...") instead of imperative mood |
| High | no | tone-and-audience | `plugins/self-assess/agents/arch-health-auditor.md:9` | Agent body written in second person ("You are...") instead of imperative mood |
| High | no | tone-and-audience | `plugins/self-assess/agents/business-rules-miner.md:9` | Agent body written in second person ("You are...") instead of imperative mood |
| High | no | tone-and-audience | `plugins/self-assess/agents/ci-topology-auditor.md:9` | Agent body written in second person ("You are...") instead of imperative mood |
| High | no | tone-and-audience | `plugins/self-assess/agents/complexity-surveyor.md:9` | Agent body written in second person ("You are...") instead of imperative mood |
| High | no | tone-and-audience | `plugins/self-assess/agents/convention-auditor.md:9` | Agent body written in second person ("You are...") instead of imperative mood |
| High | no | tone-and-audience | `plugins/self-assess/agents/docs-drift-auditor.md:9` | Agent body written in second person ("You are...") instead of imperative mood |
| High | no | tone-and-audience | `plugins/self-assess/agents/idiom-auditor.md:9` | Agent body written in second person ("You are...") instead of imperative mood |
| High | no | tone-and-audience | `plugins/self-assess/agents/idiom-remediator.md:9` | Agent body written in second person ("You are...") instead of imperative mood |
| High | no | tone-and-audience | `plugins/self-assess/agents/stage-mapper.md:9` | Agent body written in second person ("You are...") instead of imperative mood |
| High | no | tone-and-audience | `plugins/self-assess/agents/transform-executor.md:9` | Agent body written in second person ("You are...") instead of imperative mood |
| High | no | tone-and-audience | `plugins/self-assess/agents/ui-auditor.md:9` | Agent body written in second person ("You are...") instead of imperative mood |
| Medium | no | versioning-of-docs | `docs/orchestration/README.md:26` | Unpinned third-party plugin behavior claim (superpowers skill/agent/hook counts) |
| Medium | no | versioning-of-docs | `docs/orchestration/README.md:31` | Unpinned third-party inventory claim (39 plugin directories in claude-plugins-official) |
| Medium | no | versioning-of-docs | `docs/orchestration/README.md:36` | Unpinned third-party plugin agent-count claims (pr-review-toolkit/feature-dev/code-modernization/claude-security) |
| Medium | no | versioning-of-docs | `docs/orchestration/references/delegation.md:36` | Unpinned third-party plugin behavior claim (superpowers agent/command/skill counts, duplicated from README.md) |
| Medium | no | versioning-of-docs | `docs/plugin-authoring/references/craft-standards.md:56` | Unpinned codebase-state count (8 of 9 plugins have assets/) |
| Medium | no | versioning-of-docs | `docs/plugin-benchmark-phase1-results.md:84` | Unpinned third-party plugin score inventory (code-modernization, superpowers, Wirasm/prp) |
| Medium | no | versioning-of-docs | `docs/plugin-benchmark-plan.md:163` | Unpinned hook/enforcement inventory (line numbers and line-count citations for pretooluse_guard.py and other hook files) |
| Medium | no | versioning-of-docs | `docs/plugin-rebuild-findings.md:21` | Unpinned enforcement-inventory measurement (8-gram overlap percentages) |
| Medium | no | versioning-of-docs | `docs/plugin-rebuild-findings.md:27` | Unpinned enforcement-ladder measurement ("Roughly 40 runs") |
| Medium | no | versioning-of-docs | `docs/plugin-rebuild-findings.md:33` | Unpinned enforcement-inventory count ("19 rules enforced; behavior moved 1 case in 5") |
| Medium | no | tone-and-audience | `plugins/andon/skills/andon-loop/SKILL.md:12` | SKILL.md body uses second-person "you" instead of imperative mood |
| Medium | no | tone-and-audience | `plugins/andon/skills/andon-preflight/SKILL.md:24` | SKILL.md body uses second-person "you" instead of imperative mood |
| Medium | no | tone-and-audience | `plugins/andon/skills/andon-propose/SKILL.md:24` | SKILL.md body uses second-person "you" instead of imperative mood |
| Medium | no | tone-and-audience | `plugins/andon/skills/andon-status/SKILL.md:11` | SKILL.md body uses second-person "you" instead of imperative mood |
| Medium | no | tone-and-audience | `plugins/andon/skills/andon-verify/SKILL.md:20` | SKILL.md body uses second-person "you" instead of imperative mood |
| Medium | no | api-reference-completeness | `plugins/cli-scaffold/README.md:157` | cli-scaffold ships a slash command not enumerated in any Commands section |
| Medium | no | tone-and-audience | `plugins/cli-scaffold/skills/cli-scaffold-compiled/SKILL.md:8` | SKILL.md body uses second-person "you" instead of imperative mood |
| Medium | no | tone-and-audience | `plugins/cli-scaffold/skills/cli-scaffold-interpreted/SKILL.md:8` | SKILL.md body uses second-person "you" instead of imperative mood |
| Medium | no | tone-and-audience | `plugins/cli-scaffold/skills/cli-scaffold-shell/SKILL.md:8` | SKILL.md body uses second-person "you" instead of imperative mood |
| Medium | no | tone-and-audience | `plugins/cli-scaffold/skills/scaffold-cli/SKILL.md:8` | SKILL.md body uses second-person "you" instead of imperative mood |
| Medium | no | tone-and-audience | `plugins/compass/skills/compass-calibrate-format/SKILL.md:27` | SKILL.md body uses second-person "you" instead of imperative mood |
| Medium | no | tone-and-audience | `plugins/compass/skills/compass-clarify-scope/SKILL.md:35` | SKILL.md body uses second-person "you" instead of imperative mood |
| Medium | no | tone-and-audience | `plugins/compass/skills/compass-draft-revise/SKILL.md:36` | SKILL.md body uses second-person "you" instead of imperative mood |
| Medium | no | tone-and-audience | `plugins/compass/skills/compass-explore-branches/SKILL.md:34` | SKILL.md body uses second-person "you" instead of imperative mood |
| Medium | no | tone-and-audience | `plugins/compass/skills/compass-investigate-dynamically/SKILL.md:21` | SKILL.md body uses second-person "you" instead of imperative mood |
| Medium | no | tone-and-audience | `plugins/compass/skills/compass-reason-verify/SKILL.md:62` | SKILL.md body uses second-person "you" instead of imperative mood |
| Medium | no | tone-and-audience | `plugins/compass/skills/compass-solve/SKILL.md:31` | SKILL.md body uses second-person "you" instead of imperative mood |
| Medium | no | tone-and-audience | `plugins/confab/skills/confab-assertion-audit/SKILL.md:29` | SKILL.md body uses second-person "you" instead of imperative mood |
| Medium | no | tone-and-audience | `plugins/confab/skills/confab-contract-drift/SKILL.md:45` | SKILL.md body uses second-person "you" instead of imperative mood |
| Medium | no | tone-and-audience | `plugins/confab/skills/confab-cycle/SKILL.md:12` | SKILL.md body uses second-person "you" instead of imperative mood |
| Medium | no | tone-and-audience | `plugins/confab/skills/confab-dependency-audit/SKILL.md:11` | SKILL.md body uses second-person "you" instead of imperative mood |
| Medium | no | tone-and-audience | `plugins/confab/skills/confab-preflight/SKILL.md:20` | SKILL.md body uses second-person "you" instead of imperative mood |
| Medium | no | tone-and-audience | `plugins/confab/skills/confab-status/SKILL.md:41` | SKILL.md body uses second-person "you" instead of imperative mood |
| Medium | no | tone-and-audience | `plugins/cupertino/skills/cupertino-backwards/SKILL.md:12` | SKILL.md body uses second-person "you" instead of imperative mood |
| Medium | no | tone-and-audience | `plugins/cupertino/skills/cupertino-cannibalize/SKILL.md:6` | SKILL.md body uses second-person "you" instead of imperative mood |
| Medium | no | tone-and-audience | `plugins/cupertino/skills/cupertino-council/SKILL.md:6` | SKILL.md body uses second-person "you" instead of imperative mood |
| Medium | no | tone-and-audience | `plugins/cupertino/skills/cupertino-elevate/SKILL.md:16` | SKILL.md body uses second-person "you" instead of imperative mood |
| Medium | no | tone-and-audience | `plugins/cupertino/skills/cupertino-focus/SKILL.md:8` | SKILL.md body uses second-person "you" instead of imperative mood |
| Medium | no | tone-and-audience | `plugins/cupertino/skills/cupertino-handbook-draft/SKILL.md:20` | SKILL.md body uses second-person "you" instead of imperative mood |
| Medium | no | tone-and-audience | `plugins/cupertino/skills/cupertino-handbook-fix/SKILL.md:10` | SKILL.md body uses second-person "you" instead of imperative mood |
| Medium | no | tone-and-audience | `plugins/cupertino/skills/cupertino-integrate/SKILL.md:16` | SKILL.md body uses second-person "you" instead of imperative mood |
| Medium | no | tone-and-audience | `plugins/cupertino/skills/cupertino-prototype/SKILL.md:6` | SKILL.md body uses second-person "you" instead of imperative mood |
| Medium | no | tone-and-audience | `plugins/cupertino/skills/cupertino-unbox/SKILL.md:10` | SKILL.md body uses second-person "you" instead of imperative mood |
| Medium | no | versioning-of-docs | `plugins/lehre/README.md:12` | Unpinned third-party plugin behavior claim (superpowers skill/hook count, duplicated again) |
| Medium | no | tone-and-audience | `plugins/lehre/skills/lehre-codify/SKILL.md:44` | SKILL.md body uses second-person "you" instead of imperative mood |
| Medium | no | tone-and-audience | `plugins/lehre/skills/lehre-gauge/SKILL.md:91` | SKILL.md body uses second-person "you" instead of imperative mood |
| Medium | no | tone-and-audience | `plugins/lehre/skills/lehre-validate/SKILL.md:13` | SKILL.md body uses second-person "you" instead of imperative mood |
| Medium | no | tone-and-audience | `plugins/self-assess/skills/self-assess-autopilot/SKILL.md:27` | SKILL.md body uses second-person "you" instead of imperative mood |
| Medium | no | tone-and-audience | `plugins/self-assess/skills/self-assess-transform-execute/SKILL.md:54` | SKILL.md body uses second-person "you" instead of imperative mood |
| Low | no | versioning-of-docs | `docs/plugin-authoring/references/craft-standards.md:88` | Unpinned codebase-state count (63 SKILL.md files) |
| Low | no | versioning-of-docs | `docs/plugin-authoring/references/craft-standards.md:150` | Unpinned codebase-state count (Resources-section gap across 63 SKILL.md files) |
| Low | no | tone-and-audience | `plugins/cupertino/skills/cupertino-review/SKILL.md:13` | SKILL.md heading uses second-person "you" instead of imperative mood |
| Low | no | versioning-of-docs | `plugins/self-assess/README.md:245` | Unpinned codebase-state count (16 skills / 11 agents) |

## Details

### `plugins/lehre/README.md:1` — lehre README has no Skills or Agents section at all

**Dimension:** api-reference-completeness · **Severity:** High · **Mechanical:** False

**Evidence:** `grep -n "^## " plugins/lehre/README.md` returns: Why this exists, What it is not, Install, Two entry modes, What is enforced and what is not, The doctrine map, The guard protects its own control plane, Rule provenance, The check vocabulary is closed, Example Prompts, Verifying a change to this plugin, Escape hatch -- no heading named 'Skills' or 'Agents' anywhere in the file, even though plugins/lehre/skills/ contains 9 skill directories (lehre-brief, lehre-codify, lehre-conform, lehre-decompose, lehre-gauge, lehre-pin, lehre-preflight, lehre-status, lehre-validate) and plugins/lehre/agents/ contains 8 agent files (conformance-remediator.md, doctrine-researcher.md, pattern-investigator.md, rule-critic.md, spec-decomposer.md, spec-fidelity-auditor.md, violation-auditor.md, violation-verifier.md).

**Suggested fix:** Add a '## Skills (9)' section enumerating lehre-brief, lehre-codify, lehre-conform, lehre-decompose, lehre-gauge, lehre-pin, lehre-preflight, lehre-status, lehre-validate, and a '## Agents (8)' section enumerating conformance-remediator, doctrine-researcher, pattern-investigator, rule-critic, spec-decomposer, spec-fidelity-auditor, violation-auditor, violation-verifier, each with a one-line purpose, matching the style used in the other eight plugin READMEs.

### `plugins/cli-scaffold/README.md:157` — cli-scaffold ships a slash command not enumerated in any Commands section

**Dimension:** api-reference-completeness · **Severity:** Medium · **Mechanical:** False

**Evidence:** plugins/cli-scaffold/commands/cli-scaffold.md exists on disk (frontmatter: name: cli-scaffold, description: 'Scaffold a production-grade CLI...'), but plugins/cli-scaffold/README.md's heading list (`grep -n "^#" README.md`) contains no '## Commands' or combined 'Skills/Commands' heading -- the command is only referenced informally in prose/example prompts ('/cli-scaffold rust called myapp'), never enumerated as a shipped command the way the '## Skills (5)' (line 157) and '## Agents (1)' (line 167) sections enumerate skills and agents.

**Suggested fix:** Add a '## Commands (1)' section (or fold it into a combined 'Skills/Commands' heading) that lists `/cli-scaffold` with a one-line description of what it dispatches, consistent with codebase-consistency's README '## Commands' section style.

### `plugins/self-assess/agents/complexity-surveyor.md:9` — Agent body written in second person ("You are...") instead of imperative mood

**Dimension:** tone-and-audience · **Severity:** High · **Mechanical:** False

**Evidence:** You are complexity-surveyor, a size and structural-complexity measurer. You report SLOC, file

**Suggested fix:** Rewrite the agent body from a second-person persona ("You are X, you do Y") to imperative/infinitive instructions addressed to the acting agent (e.g. "Do Y."), throughout the file — not just the cited line.

### `plugins/self-assess/agents/ci-topology-auditor.md:9` — Agent body written in second person ("You are...") instead of imperative mood

**Dimension:** tone-and-audience · **Severity:** High · **Mechanical:** False

**Evidence:** You are ci-topology-auditor, a git-remote and CI-configuration auditor. You find redundant or

**Suggested fix:** Rewrite the agent body from a second-person persona to imperative/infinitive instructions throughout the file.

### `plugins/self-assess/agents/stage-mapper.md:9` — Agent body written in second person ("You are...") instead of imperative mood

**Dimension:** tone-and-audience · **Severity:** High · **Mechanical:** False

**Evidence:** You are stage-mapper, an architecture-graph extraction specialist. You build the REAL import/use

**Suggested fix:** Rewrite the agent body from a second-person persona to imperative/infinitive instructions throughout the file.

### `plugins/self-assess/agents/idiom-remediator.md:9` — Agent body written in second person ("You are...") instead of imperative mood

**Dimension:** tone-and-audience · **Severity:** High · **Mechanical:** False

**Evidence:** You are idiom-remediator, a mechanical idiom-rewrite applier. You are handed one cluster of

**Suggested fix:** Rewrite the agent body from a second-person persona to imperative/infinitive instructions throughout the file.

### `plugins/self-assess/agents/docs-drift-auditor.md:9` — Agent body written in second person ("You are...") instead of imperative mood

**Dimension:** tone-and-audience · **Severity:** High · **Mechanical:** False

**Evidence:** You are docs-drift-auditor, a documentation-accuracy verifier. You check whether a falsifiable

**Suggested fix:** Rewrite the agent body from a second-person persona to imperative/infinitive instructions throughout the file.

### `plugins/self-assess/agents/transform-executor.md:9` — Agent body written in second person ("You are...") instead of imperative mood

**Dimension:** tone-and-audience · **Severity:** High · **Mechanical:** False

**Evidence:** You are transform-executor, the only Write/Edit-capable agent in self-assess. You apply exactly

**Suggested fix:** Rewrite the agent body from a second-person persona to imperative/infinitive instructions throughout the file.

### `plugins/self-assess/agents/convention-auditor.md:9` — Agent body written in second person ("You are...") instead of imperative mood

**Dimension:** tone-and-audience · **Severity:** High · **Mechanical:** False

**Evidence:** You are convention-auditor, a documented-conventions compliance checker. You verify that code

**Suggested fix:** Rewrite the agent body from a second-person persona to imperative/infinitive instructions throughout the file.

### `plugins/self-assess/agents/ui-auditor.md:9` — Agent body written in second person ("You are...") instead of imperative mood

**Dimension:** tone-and-audience · **Severity:** High · **Mechanical:** False

**Evidence:** You are ui-auditor, a static UI-quality auditor. You read component/template/stylesheet source

**Suggested fix:** Rewrite the agent body from a second-person persona to imperative/infinitive instructions throughout the file.

### `plugins/self-assess/agents/business-rules-miner.md:9` — Agent body written in second person ("You are...") instead of imperative mood

**Dimension:** tone-and-audience · **Severity:** High · **Mechanical:** False

**Evidence:** You are business-rules-miner, a domain-logic extraction specialist. You mine calculations,

**Suggested fix:** Rewrite the agent body from a second-person persona to imperative/infinitive instructions throughout the file.

### `plugins/self-assess/agents/arch-health-auditor.md:9` — Agent body written in second person ("You are...") instead of imperative mood

**Dimension:** tone-and-audience · **Severity:** High · **Mechanical:** False

**Evidence:** You are arch-health-auditor, a dependency-graph deficiency judge. You take structural signals

**Suggested fix:** Rewrite the agent body from a second-person persona to imperative/infinitive instructions throughout the file.

### `plugins/self-assess/agents/idiom-auditor.md:9` — Agent body written in second person ("You are...") instead of imperative mood

**Dimension:** tone-and-audience · **Severity:** High · **Mechanical:** False

**Evidence:** You are idiom-auditor, a language-idiom and code-smell finder. You judge whether code is

**Suggested fix:** Rewrite the agent body from a second-person persona to imperative/infinitive instructions throughout the file.

### `plugins/andon/skills/andon-verify/SKILL.md:20` — SKILL.md body uses second-person "you" instead of imperative mood

**Dimension:** tone-and-audience · **Severity:** Medium · **Mechanical:** False

**Evidence:** `signals` are booleans you determine by reading the wire's contract:

**Suggested fix:** Rewrite this sentence (and any other second-person phrasing in the file) into imperative/infinitive form.

### `plugins/andon/skills/andon-loop/SKILL.md:12` — SKILL.md body uses second-person "you" instead of imperative mood

**Dimension:** tone-and-audience · **Severity:** Medium · **Mechanical:** False

**Evidence:** structured results for you (the orchestrator) to persist -- never call them

**Suggested fix:** Rewrite this sentence (and any other second-person phrasing in the file) into imperative/infinitive form.

### `plugins/andon/skills/andon-status/SKILL.md:11` — SKILL.md body uses second-person "you" instead of imperative mood

**Dimension:** tone-and-audience · **Severity:** Medium · **Mechanical:** False

**Evidence:** pass. Read settings first so you look in the right place:

**Suggested fix:** Rewrite this sentence (and any other second-person phrasing in the file) into imperative/infinitive form.

### `plugins/andon/skills/andon-preflight/SKILL.md:24` — SKILL.md body uses second-person "you" instead of imperative mood

**Dimension:** tone-and-audience · **Severity:** Medium · **Mechanical:** False

**Evidence:** Determine availability flags by inspection (do this yourself; the script

**Suggested fix:** Rewrite this sentence (and any other second-person phrasing in the file) into imperative/infinitive form.

### `plugins/andon/skills/andon-propose/SKILL.md:24` — SKILL.md body uses second-person "you" instead of imperative mood

**Dimension:** tone-and-audience · **Severity:** Medium · **Mechanical:** False

**Evidence:** yourself.

**Suggested fix:** Rewrite this sentence (and any other second-person phrasing in the file) into imperative/infinitive form.

### `plugins/confab/agents/agentic-reliability-auditor.md:7` — Agent body written in second person ("You are...") instead of imperative mood

**Dimension:** tone-and-audience · **Severity:** High · **Mechanical:** False

**Evidence:** You audit a repository's own agentic definitions — files under `skills/`,

**Suggested fix:** Rewrite the agent body from a second-person persona to imperative/infinitive instructions throughout the file.

### `plugins/confab/agents/confab-remediator.md:7` — Agent body written in second person ("You are...") instead of imperative mood

**Dimension:** tone-and-audience · **Severity:** High · **Mechanical:** False

**Evidence:** You are handed exactly ONE finding and apply exactly ONE fix for it. You

**Suggested fix:** Rewrite the agent body from a second-person persona to imperative/infinitive instructions throughout the file.

### `plugins/confab/agents/contract-auditor.md:7` — Agent body written in second person ("You are...") instead of imperative mood

**Dimension:** tone-and-audience · **Severity:** High · **Mechanical:** False

**Evidence:** You find drift between a declared, machine-checkable contract and how

**Suggested fix:** Rewrite the agent body from a second-person persona to imperative/infinitive instructions throughout the file.

### `plugins/confab/agents/dependency-auditor.md:7` — Agent body written in second person ("You are...") instead of imperative mood

**Dimension:** tone-and-audience · **Severity:** High · **Mechanical:** False

**Evidence:** You verify that declared package dependencies actually exist in their

**Suggested fix:** Rewrite the agent body from a second-person persona to imperative/infinitive instructions throughout the file.

### `plugins/confab/agents/assertion-auditor.md:7` — Agent body written in second person ("You are...") instead of imperative mood

**Dimension:** tone-and-audience · **Severity:** High · **Mechanical:** False

**Evidence:** You determine whether a test suite would catch specific, plausible

**Suggested fix:** Rewrite the agent body from a second-person persona to imperative/infinitive instructions throughout the file.

### `plugins/cli-scaffold/agents/cli-scaffold-verifier.md:39` — Agent body written in second person ("You are...") instead of imperative mood

**Dimension:** tone-and-audience · **Severity:** High · **Mechanical:** False

**Evidence:** You are the **cli-scaffold-verifier**. You perform a **read-only** conformance

**Suggested fix:** Rewrite the agent body from a second-person persona to imperative/infinitive instructions throughout the file.

### `plugins/confab/skills/confab-assertion-audit/SKILL.md:29` — SKILL.md body uses second-person "you" instead of imperative mood

**Dimension:** tone-and-audience · **Severity:** Medium · **Mechanical:** False

**Evidence:** per Find-phase finding (or as a batch if your dispatch prompt makes the

**Suggested fix:** Rewrite this sentence (and any other second-person phrasing in the file) into imperative/infinitive form.

### `plugins/confab/skills/confab-status/SKILL.md:41` — SKILL.md body uses second-person "you" instead of imperative mood

**Dimension:** tone-and-audience · **Severity:** Medium · **Mechanical:** False

**Evidence:** 5. Surface the `suggestion` field as your one recommended next action —

**Suggested fix:** Rewrite this sentence (and any other second-person phrasing in the file) into imperative/infinitive form.

### `plugins/confab/skills/confab-cycle/SKILL.md:12` — SKILL.md body uses second-person "you" instead of imperative mood

**Dimension:** tone-and-audience · **Severity:** Medium · **Mechanical:** False

**Evidence:** describes how to drive that engine. If your own count of passes ever

**Suggested fix:** Rewrite this sentence (and any other second-person phrasing in the file) into imperative/infinitive form.

### `plugins/confab/skills/confab-contract-drift/SKILL.md:45` — SKILL.md body uses second-person "you" instead of imperative mood

**Dimension:** tone-and-audience · **Severity:** Medium · **Mechanical:** False

**Evidence:** `true`, say so explicitly in your summary — an unverified contract-

**Suggested fix:** Rewrite this sentence (and any other second-person phrasing in the file) into imperative/infinitive form.

### `plugins/confab/skills/confab-dependency-audit/SKILL.md:11` — SKILL.md body uses second-person "you" instead of imperative mood

**Dimension:** tone-and-audience · **Severity:** Medium · **Mechanical:** False

**Evidence:** instructions. Your job is to orchestrate the agent judgment layer around

**Suggested fix:** Rewrite this sentence (and any other second-person phrasing in the file) into imperative/infinitive form.

### `plugins/confab/skills/confab-preflight/SKILL.md:20` — SKILL.md body uses second-person "you" instead of imperative mood

**Dimension:** tone-and-audience · **Severity:** Medium · **Mechanical:** False

**Evidence:** setting you already know about) specifies a value other than the

**Suggested fix:** Rewrite this sentence (and any other second-person phrasing in the file) into imperative/infinitive form.

### `plugins/cli-scaffold/skills/cli-scaffold-shell/SKILL.md:8` — SKILL.md body uses second-person "you" instead of imperative mood

**Dimension:** tone-and-audience · **Severity:** Medium · **Mechanical:** False

**Evidence:** You generate a CLI in a shell dialect. All rules come from the

**Suggested fix:** Rewrite this sentence (and any other second-person phrasing in the file) into imperative/infinitive form.

### `plugins/cli-scaffold/skills/cli-scaffold-interpreted/SKILL.md:8` — SKILL.md body uses second-person "you" instead of imperative mood

**Dimension:** tone-and-audience · **Severity:** Medium · **Mechanical:** False

**Evidence:** You generate a CLI in one of the six interpreted languages. All rules come from

**Suggested fix:** Rewrite this sentence (and any other second-person phrasing in the file) into imperative/infinitive form.

### `plugins/cli-scaffold/skills/cli-scaffold-compiled/SKILL.md:8` — SKILL.md body uses second-person "you" instead of imperative mood

**Dimension:** tone-and-audience · **Severity:** Medium · **Mechanical:** False

**Evidence:** You generate a CLI in Rust, Go, or .NET. All rules come from the

**Suggested fix:** Rewrite this sentence (and any other second-person phrasing in the file) into imperative/infinitive form.

### `plugins/cli-scaffold/skills/scaffold-cli/SKILL.md:8` — SKILL.md body uses second-person "you" instead of imperative mood

**Dimension:** tone-and-audience · **Severity:** Medium · **Mechanical:** False

**Evidence:** You route a scaffold request to the correct paradigm skill. You never generate

**Suggested fix:** Rewrite this sentence (and any other second-person phrasing in the file) into imperative/infinitive form, e.g. "Route a scaffold request... Never generate code directly."

### `plugins/self-assess/skills/self-assess-autopilot/SKILL.md:27` — SKILL.md body uses second-person "you" instead of imperative mood

**Dimension:** tone-and-audience · **Severity:** Medium · **Mechanical:** False

**Evidence:** latest commit. Tell the user you're reusing the existing stage map rather than silently

**Suggested fix:** Rewrite this sentence (and any other second-person phrasing in the file) into imperative/infinitive form.

### `plugins/self-assess/skills/self-assess-transform-execute/SKILL.md:54` — SKILL.md body uses second-person "you" instead of imperative mood

**Dimension:** tone-and-audience · **Severity:** Medium · **Mechanical:** False

**Evidence:** `.claude/self-assess.local.md` AND you have told them plainly what changed paths exist. A

**Suggested fix:** Rewrite this sentence (and any other second-person phrasing in the file) into imperative/infinitive form.

### `plugins/compass/agents/branch-proposer.md:17` — Agent body written in second person ("You are...") instead of imperative mood

**Dimension:** tone-and-audience · **Severity:** High · **Mechanical:** False

**Evidence:** You do exactly ONE of two jobs per dispatch, stated in your prompt: **Propose** or

**Suggested fix:** Rewrite the agent body from a second-person persona to imperative/infinitive instructions throughout the file.

### `plugins/compass/agents/instruction-candidate.md:17` — Agent body written in second person ("You are...") instead of imperative mood

**Dimension:** tone-and-audience · **Severity:** High · **Mechanical:** False

**Evidence:** You do exactly ONE of three jobs per dispatch, named in your prompt: **Draft**,

**Suggested fix:** Rewrite the agent body from a second-person persona to imperative/infinitive instructions throughout the file.

### `plugins/compass/agents/reasoning-path.md:16` — Agent body written in second person ("You are...") instead of imperative mood

**Dimension:** tone-and-audience · **Severity:** High · **Mechanical:** False

**Evidence:** You produce **exactly one** reasoning attempt under the **strategy named in your

**Suggested fix:** Rewrite the agent body from a second-person persona to imperative/infinitive instructions throughout the file.

### `plugins/lehre/agents/violation-verifier.md:9` — Agent body written in second person ("You are...") instead of imperative mood

**Dimension:** tone-and-audience · **Severity:** High · **Mechanical:** False

**Evidence:** You open one location and answer one question: is the reported violation real?

**Suggested fix:** Rewrite the agent body from a second-person persona to imperative/infinitive instructions throughout the file.

### `plugins/lehre/agents/doctrine-researcher.md:9` — Agent body written in second person ("You are...") instead of imperative mood

**Dimension:** tone-and-audience · **Severity:** High · **Mechanical:** False

**Evidence:** You research one rule-domain and return candidate rules, each resting on a named

**Suggested fix:** Rewrite the agent body from a second-person persona to imperative/infinitive instructions throughout the file.

### `plugins/lehre/agents/spec-decomposer.md:9` — Agent body written in second person ("You are...") instead of imperative mood

**Dimension:** tone-and-audience · **Severity:** High · **Mechanical:** False

**Evidence:** You turn one concern of a stated project intent into candidate build units. You never

**Suggested fix:** Rewrite the agent body from a second-person persona to imperative/infinitive instructions throughout the file.

### `plugins/lehre/agents/spec-fidelity-auditor.md:9` — Agent body written in second person ("You are...") instead of imperative mood

**Dimension:** tone-and-audience · **Severity:** High · **Mechanical:** False

**Evidence:** You answer the one question the doctrine structurally cannot: does this unit do what it

**Suggested fix:** Rewrite the agent body from a second-person persona to imperative/infinitive instructions throughout the file.

### `plugins/lehre/agents/pattern-investigator.md:9` — Agent body written in second person ("You are...") instead of imperative mood

**Dimension:** tone-and-audience · **Severity:** High · **Mechanical:** False

**Evidence:** You report what this codebase actually does, with citations. You never say what it

**Suggested fix:** Rewrite the agent body from a second-person persona to imperative/infinitive instructions throughout the file.

### `plugins/lehre/agents/conformance-remediator.md:9` — Agent body written in second person ("You are...") instead of imperative mood

**Dimension:** tone-and-audience · **Severity:** High · **Mechanical:** False

**Evidence:** You apply one determined rewrite at cited locations in one file, and stop.

**Suggested fix:** Rewrite the agent body from a second-person persona to imperative/infinitive instructions throughout the file.

### `plugins/lehre/agents/rule-critic.md:9` — Agent body written in second person ("You are...") instead of imperative mood

**Dimension:** tone-and-audience · **Severity:** High · **Mechanical:** False

**Evidence:** You try to refute candidate rules. Default to refuted when uncertain: a rule that

**Suggested fix:** Rewrite the agent body from a second-person persona to imperative/infinitive instructions throughout the file.

### `plugins/lehre/agents/violation-auditor.md:9` — Agent body written in second person ("You are...") instead of imperative mood

**Dimension:** tone-and-audience · **Severity:** High · **Mechanical:** False

**Evidence:** You find violations of exactly one `judgement`-kind rule — a rule whose `check` block

**Suggested fix:** Rewrite the agent body from a second-person persona to imperative/infinitive instructions throughout the file.

### `plugins/cupertino/agents/handbook-remediator.md:9` — Agent body written in second person ("You are...") instead of imperative mood

**Dimension:** tone-and-audience · **Severity:** High · **Mechanical:** False

**Evidence:** You apply mechanical fixes at exact, already-cited locations. You do not decide what to fix — that decision was already made by cupertino-handbook-check's findings, and you were only handed the ones marked `mechanical: true`.

**Suggested fix:** Rewrite the agent body from a second-person persona to imperative/infinitive instructions throughout the file.

### `plugins/cupertino/agents/handbook-drift-auditor.md:9` — Agent body written in second person ("You are...") instead of imperative mood

**Dimension:** tone-and-audience · **Severity:** High · **Mechanical:** False

**Evidence:** You check files against exactly one handbook rule per dispatch. The dispatching prompt always contains a line of the form `RULE: <rule text>` and a list of target files. If it names more than one rule, note that the rest are out of scope and check only the first; never propose a finding against a rule you were not asked to check.

**Suggested fix:** Rewrite the agent body from a second-person persona to imperative/infinitive instructions throughout the file.

### `plugins/cupertino/agents/handbook-dimension-analyst.md:9` — Agent body written in second person ("You are...") instead of imperative mood

**Dimension:** tone-and-audience · **Severity:** High · **Mechanical:** False

**Evidence:** You analyze exactly one handbook dimension per dispatch. The dispatching prompt always contains a line of the form `DIMENSION: <name>`. If it contains more than one such line, treat every dimension after the first as out of scope: note in your output that the rest were not analyzed in this dispatch, then continue with only the first.

**Suggested fix:** Rewrite the agent body from a second-person persona to imperative/infinitive instructions throughout the file.

### `plugins/cupertino/agents/handbook-verifier.md:9` — Agent body written in second person ("You are...") instead of imperative mood

**Dimension:** tone-and-audience · **Severity:** High · **Mechanical:** False

**Evidence:** You judge whether one specific location now complies with one specific rule. You were deliberately not told what the remediator did, why, or how confident it was — do not seek that out, do not guess at it, and do not reconstruct it from context. Judge only what you can see by reading the file's current state yourself.

**Suggested fix:** Rewrite the agent body from a second-person persona to imperative/infinitive instructions throughout the file.

### `plugins/codebase-consistency/agents/pattern-analyst.md:7` — Agent body written in second person ("You are...") instead of imperative mood

**Dimension:** tone-and-audience · **Severity:** High · **Mechanical:** False

**Evidence:** You are a senior code archaeologist. Your job is **understanding, not

**Suggested fix:** Rewrite the agent body from a second-person persona to imperative/infinitive instructions throughout the file.

### `plugins/codebase-consistency/agents/consistency-critic.md:7` — Agent body written in second person ("You are...") instead of imperative mood

**Dimension:** tone-and-audience · **Severity:** High · **Mechanical:** False

**Evidence:** You are a principal engineer reviewing someone else's "let's make this

**Suggested fix:** Rewrite the agent body from a second-person persona to imperative/infinitive instructions throughout the file.

### `plugins/codebase-consistency/agents/align-executor.md:7` — Agent body written in second person ("You are...") instead of imperative mood

**Dimension:** tone-and-audience · **Severity:** High · **Mechanical:** False

**Evidence:** You are converting **one module** (one node in the dependency graph) of an

**Suggested fix:** Rewrite the agent body (e.g. "Convert one module...") to imperative/infinitive instructions throughout the file — the whole file, including 'Your job', 'you're handed', 'your module', is second person.

### `plugins/codebase-consistency/agents/pattern-extractor.md:7` — Agent body written in second person ("You are...") instead of imperative mood

**Dimension:** tone-and-audience · **Severity:** High · **Mechanical:** False

**Evidence:** You are a pattern-extractor. Your job is to look at every variant of one

**Suggested fix:** Rewrite the agent body from a second-person persona to imperative/infinitive instructions throughout the file.

### `plugins/codebase-consistency/agents/equivalence-verifier.md:7` — Agent body written in second person ("You are...") instead of imperative mood

**Dimension:** tone-and-audience · **Severity:** High · **Mechanical:** False

**Evidence:** You are an equivalence verifier. A module has just been aligned to a

**Suggested fix:** Rewrite the agent body from a second-person persona to imperative/infinitive instructions throughout the file.

### `plugins/andon/agents/andon-challenger.md:12` — Agent body written in second person ("You are...") instead of imperative mood

**Dimension:** tone-and-audience · **Severity:** High · **Mechanical:** False

**Evidence:** You are the opposing side of an adversarial duel proving or refuting a

**Suggested fix:** Rewrite the agent body from a second-person persona to imperative/infinitive instructions throughout the file.

### `plugins/andon/agents/andon-adjudicator.md:12` — Agent body written in second person ("You are...") instead of imperative mood

**Dimension:** tone-and-audience · **Severity:** High · **Mechanical:** False

**Evidence:** You render the tribunal's verdict. You read all three prior outputs

**Suggested fix:** Rewrite the agent body from a second-person persona to imperative/infinitive instructions throughout the file.

### `plugins/andon/agents/andon-verifier.md:13` — Agent body written in second person ("You are...") instead of imperative mood

**Dimension:** tone-and-audience · **Severity:** High · **Mechanical:** False

**Evidence:** Your job is narrower than the Defender's or Challenger's: take their claims

**Suggested fix:** Rewrite the agent body from a second-person persona to imperative/infinitive instructions throughout the file.

### `plugins/andon/agents/andon-defender.md:12` — Agent body written in second person ("You are...") instead of imperative mood

**Dimension:** tone-and-audience · **Severity:** High · **Mechanical:** False

**Evidence:** You are one side of an adversarial duel proving or refuting a wire's fix.

**Suggested fix:** Rewrite the agent body from a second-person persona to imperative/infinitive instructions throughout the file.

### `plugins/lehre/skills/lehre-codify/SKILL.md:44` — SKILL.md body uses second-person "you" instead of imperative mood

**Dimension:** tone-and-audience · **Severity:** Medium · **Mechanical:** False

**Evidence:** what it refutes. Do not argue with it on the strength of your own draft.

**Suggested fix:** Rewrite this sentence (and any other second-person phrasing in the file) into imperative/infinitive form.

### `plugins/lehre/skills/lehre-gauge/SKILL.md:91` — SKILL.md body uses second-person "you" instead of imperative mood

**Dimension:** tone-and-audience · **Severity:** Medium · **Mechanical:** False

**Evidence:** previous output in place; confirm the numbers came from the run you think

**Suggested fix:** Rewrite this sentence (and any other second-person phrasing in the file) into imperative/infinitive form.

### `plugins/lehre/skills/lehre-validate/SKILL.md:13` — SKILL.md body uses second-person "you" instead of imperative mood

**Dimension:** tone-and-audience · **Severity:** Medium · **Mechanical:** False

**Evidence:** 1. **Never validate work you just did in the same reasoning pass.** Dispatch the

**Suggested fix:** Rewrite this sentence (and any other second-person phrasing in the file) into imperative/infinitive form.

### `plugins/compass/skills/compass-investigate-dynamically/SKILL.md:21` — SKILL.md body uses second-person "you" instead of imperative mood

**Dimension:** tone-and-audience · **Severity:** Medium · **Mechanical:** False

**Evidence:** - **Reasoning** — name the specific remaining unknown you are trying to close.

**Suggested fix:** Rewrite this sentence (and any other second-person phrasing in the file) into imperative/infinitive form.

### `plugins/compass/skills/compass-reason-verify/SKILL.md:62` — SKILL.md body uses second-person "you" instead of imperative mood

**Dimension:** tone-and-audience · **Severity:** Medium · **Mechanical:** False

**Evidence:** agents in parallel and votes. Otherwise dispatch three isolated attempts yourself

**Suggested fix:** Rewrite this sentence (and any other second-person phrasing in the file) into imperative/infinitive form.

### `plugins/compass/skills/compass-clarify-scope/SKILL.md:35` — SKILL.md body uses second-person "you" instead of imperative mood

**Dimension:** tone-and-audience · **Severity:** Medium · **Mechanical:** False

**Evidence:** `clarify` check computes `flagged` per entry — you do not eyeball it.

**Suggested fix:** Rewrite this sentence (and any other second-person phrasing in the file) into imperative/infinitive form.

### `plugins/compass/skills/compass-explore-branches/SKILL.md:34` — SKILL.md body uses second-person "you" instead of imperative mood

**Dimension:** tone-and-audience · **Severity:** Medium · **Mechanical:** False

**Evidence:** size check itself, so this is your judgment call, not its.

**Suggested fix:** Rewrite this sentence (and any other second-person phrasing in the file) into imperative/infinitive form.

### `plugins/compass/skills/compass-calibrate-format/SKILL.md:27` — SKILL.md body uses second-person "you" instead of imperative mood

**Dimension:** tone-and-audience · **Severity:** Medium · **Mechanical:** False

**Evidence:** - If you must **construct** the set, include a **happy path** and **at least one

**Suggested fix:** Rewrite this sentence (and any other second-person phrasing in the file) into imperative/infinitive form.

### `plugins/compass/skills/compass-solve/SKILL.md:31` — SKILL.md body uses second-person "you" instead of imperative mood

**Dimension:** tone-and-audience · **Severity:** Medium · **Mechanical:** False

**Evidence:** before you invoke it — the script runs to completion in one shot; it cannot pause

**Suggested fix:** Rewrite this sentence (and any other second-person phrasing in the file) into imperative/infinitive form.

### `plugins/compass/skills/compass-draft-revise/SKILL.md:36` — SKILL.md body uses second-person "you" instead of imperative mood

**Dimension:** tone-and-audience · **Severity:** Medium · **Mechanical:** False

**Evidence:** - The guard returns `revise` (criteria at or below threshold — the only ones you

**Suggested fix:** Rewrite this sentence (and any other second-person phrasing in the file) into imperative/infinitive form.

### `plugins/cupertino/skills/cupertino-unbox/SKILL.md:10` — SKILL.md body uses second-person "you" instead of imperative mood

**Dimension:** tone-and-audience · **Severity:** Medium · **Mechanical:** False

**Evidence:** If you haven't verified the real sequence (by reading the actual code path or running it), don't guess at it — go look.

**Suggested fix:** Rewrite this sentence (and any other second-person phrasing in the file) into imperative/infinitive form.

### `plugins/cupertino/skills/cupertino-council/SKILL.md:6` — SKILL.md body uses second-person "you" instead of imperative mood

**Dimension:** tone-and-audience · **Severity:** Medium · **Mechanical:** False

**Evidence:** This is not decoration on top of your own design instinct — it is the design process.

**Suggested fix:** Rewrite this sentence (and any other second-person phrasing in the file) into imperative/infinitive form.

### `plugins/cupertino/skills/cupertino-cannibalize/SKILL.md:6` — SKILL.md body uses second-person "you" instead of imperative mood

**Dimension:** tone-and-audience · **Severity:** Medium · **Mechanical:** False

**Evidence:** if you see that denial, finish or exit the review pipeline first, then invoke this skill separately and explicitly.

**Suggested fix:** Rewrite this sentence (and any other second-person phrasing in the file) into imperative/infinitive form.

### `plugins/cupertino/skills/cupertino-integrate/SKILL.md:16` — SKILL.md body uses second-person "you" instead of imperative mood

**Dimension:** tone-and-audience · **Severity:** Medium · **Mechanical:** False

**Evidence:** - If delegate: name what stays friction-prone — the cost you are choosing to keep paying to a vendor/framework rather than own.

**Suggested fix:** Rewrite this sentence (and any other second-person phrasing in the file) into imperative/infinitive form.

### `plugins/cupertino/skills/cupertino-elevate/SKILL.md:16` — SKILL.md body uses second-person "you" instead of imperative mood

**Dimension:** tone-and-audience · **Severity:** Medium · **Mechanical:** False

**Evidence:** how the metaphor changes visibility (can you see it happening?), navigability (can you move through it, not just trigger it once?)

**Suggested fix:** Rewrite this sentence (and any other second-person phrasing in the file) into imperative/infinitive form.

### `plugins/cupertino/skills/cupertino-focus/SKILL.md:8` — SKILL.md body uses second-person "you" instead of imperative mood

**Dimension:** tone-and-audience · **Severity:** Medium · **Mechanical:** False

**Evidence:** If you see a denial for that reason, run `cupertino-backwards` first — do not work around the gate.

**Suggested fix:** Rewrite this sentence (and any other second-person phrasing in the file) into imperative/infinitive form.

### `plugins/cupertino/skills/cupertino-handbook-draft/SKILL.md:20` — SKILL.md body uses second-person "you" instead of imperative mood

**Dimension:** tone-and-audience · **Severity:** Medium · **Mechanical:** False

**Evidence:** Each candidate rule is then independently re-verified by a second, blind dispatch of the same agent type before you use it.

**Suggested fix:** Rewrite this sentence (and any other second-person phrasing in the file) into imperative/infinitive form.

### `plugins/cupertino/skills/cupertino-backwards/SKILL.md:12` — SKILL.md body uses second-person "you" instead of imperative mood

**Dimension:** tone-and-audience · **Severity:** Medium · **Mechanical:** False

**Evidence:** If you catch yourself reaching for one, the sentence has already smuggled in a technology answer; rewrite it in terms of what the person does or feels instead.

**Suggested fix:** Rewrite this sentence (and any other second-person phrasing in the file) into imperative/infinitive form.

### `plugins/cupertino/skills/cupertino-review/SKILL.md:13` — SKILL.md heading uses second-person "you" instead of imperative mood

**Dimension:** tone-and-audience · **Severity:** Low · **Mechanical:** False

**Evidence:** ## Before you start

**Suggested fix:** Rename heading to something like "## Before starting" or "## Prerequisites".

### `plugins/cupertino/skills/cupertino-prototype/SKILL.md:6` — SKILL.md body uses second-person "you" instead of imperative mood

**Dimension:** tone-and-audience · **Severity:** Medium · **Mechanical:** False

**Evidence:** Settle one specific empirical question by building and running something real — never by describing what you expect would happen.

**Suggested fix:** Rewrite this sentence (and any other second-person phrasing in the file) into imperative/infinitive form.

### `plugins/cupertino/skills/cupertino-handbook-fix/SKILL.md:10` — SKILL.md body uses second-person "you" instead of imperative mood

**Dimension:** tone-and-audience · **Severity:** Medium · **Mechanical:** False

**Evidence:** If you're executing this skill body, that gate already passed for this invocation — but if the user asks you to "just fix it" without having set this, **stop and report plainly**...

**Suggested fix:** Rewrite this sentence (and any other second-person phrasing in the file) into imperative/infinitive form.

### `docs/orchestration/README.md:26` — Unpinned third-party plugin behavior claim (superpowers skill/agent/hook counts)

**Dimension:** versioning-of-docs · **Severity:** Medium · **Mechanical:** False

**Evidence:** **superpowers is process discipline.** It ships 14 skills, zero agents, zero commands, and one `SessionStart` hook — so any agent, in any plugin's workflow, can execute it.

**Suggested fix:** Add a commit hash or checked-date for the superpowers repo state this count was taken from, e.g. "ships 14 skills, zero agents, zero commands (as of `obra/superpowers` commit `<hash>` / checked 2026-XX-XX)".

### `docs/orchestration/README.md:31` — Unpinned third-party inventory claim (39 plugin directories in claude-plugins-official)

**Dimension:** versioning-of-docs · **Severity:** Medium · **Mechanical:** False

**Evidence:** not one of the 39 plugin directories inside `anthropics/claude-plugins-official`.

**Suggested fix:** Pin the plugin-count claim to a commit hash or checked-date of `anthropics/claude-plugins-official`, e.g. "(39 plugin directories as of commit `<hash>`)".

### `docs/orchestration/README.md:36` — Unpinned third-party plugin agent-count claims (pr-review-toolkit/feature-dev/code-modernization/claude-security)

**Dimension:** versioning-of-docs · **Severity:** Medium · **Mechanical:** False

**Evidence:** `pr-review-toolkit` holds 6 agents behind one command, `feature-dev`
3 behind one, `code-modernization` 8 behind ten, and `claude-security` 8 behind none.

**Suggested fix:** Pin these agent/command counts to the commit hash or checked-date of `anthropics/claude-plugins-official` they were counted against.

### `docs/orchestration/references/delegation.md:36` — Unpinned third-party plugin behavior claim (superpowers agent/command/skill counts, duplicated from README.md)

**Dimension:** versioning-of-docs · **Severity:** Medium · **Mechanical:** False

**Evidence:** Superpowers itself ships zero agents and zero commands across its 14 skills — it
supplies the discipline, not the dispatch mechanism.

**Suggested fix:** Pin to the commit/checked-date of `obra/superpowers` this count reflects, matching the style used elsewhere in this repo (e.g. `as of \`claude-security@0.11.0\``).

### `plugins/lehre/README.md:12` — Unpinned third-party plugin behavior claim (superpowers skill/hook count, duplicated again)

**Dimension:** versioning-of-docs · **Severity:** Medium · **Mechanical:** False

**Evidence:** `obra/superpowers` ships 14 skills and one `SessionStart` hook, so
every rule it carries sits on the top row of the enforcement ladder this repository
measured over ~40 runs:

**Suggested fix:** Pin both the superpowers skill/hook count and the werkstoff "~40 runs" enforcement-ladder measurement to a commit hash or checked-date.

### `docs/plugin-authoring/references/craft-standards.md:56` — Unpinned codebase-state count (8 of 9 plugins have assets/)

**Dimension:** versioning-of-docs · **Severity:** Medium · **Mechanical:** False

**Evidence:** `templates/` is not used anywhere in werkstoff today; `assets/` is — 8 of the 9 plugins
(all but `takt`) have a plugin-root `assets/` directory, referenced from SKILL.md (or,
for `codebase-consistency`, a command file) via `${CLAUDE_PLUGIN_ROOT}/assets/...`.

**Suggested fix:** Pin to a commit hash or checked-date, as this same document already does at line 89 ("as of `1cd5d07`") and line 102.

### `docs/plugin-authoring/references/craft-standards.md:88` — Unpinned codebase-state count (63 SKILL.md files)

**Dimension:** versioning-of-docs · **Severity:** Low · **Mechanical:** False

**Evidence:** Followed — `name:` always matches the skill's directory name across all 63 SKILL.md files

**Suggested fix:** Add the same "as of `1cd5d07`" pin used two rows/paragraphs later in this file for the identical file-count figure.

### `docs/plugin-authoring/references/craft-standards.md:150` — Unpinned codebase-state count (Resources-section gap across 63 SKILL.md files)

**Dimension:** versioning-of-docs · **Severity:** Low · **Mechanical:** False

**Evidence:** **werkstoff status: gap, one file fixed.** Zero of werkstoff's 63 SKILL.md files had a
`## Resources` section before this pass.

**Suggested fix:** Pin this claim to the commit hash or checked-date it was measured against, consistent with this document's own pattern elsewhere (line 89, 102).

### `plugins/self-assess/README.md:245` — Unpinned codebase-state count (16 skills / 11 agents)

**Dimension:** versioning-of-docs · **Severity:** Low · **Mechanical:** False

**Evidence:** ├── skills/self-assess-*/SKILL.md   # 16 skills, one per spec entry
└── agents/*.md                     # 11 agents, one per spec entry

**Suggested fix:** Pin these skill/agent counts to a commit hash or checked-date so a later addition/removal is visible as staleness.

### `docs/plugin-rebuild-findings.md:21` — Unpinned enforcement-inventory measurement (8-gram overlap percentages)

**Dimension:** versioning-of-docs · **Severity:** Medium · **Mechanical:** False

**Evidence:** Behavior JSON carries obligations, not implementations: verbatim 8-gram overlap
with legacy is 2.3% (andon) and 4.0% (cli-scaffold), and the residue is
unavoidable domain phrasing.

**Suggested fix:** Pin the overlap percentages to the commit hash or checked-date of the behavior-JSON/legacy comparison, matching this file's own pattern used later (lines 135, 140, 150).

### `docs/plugin-rebuild-findings.md:27` — Unpinned enforcement-ladder measurement ("Roughly 40 runs")

**Dimension:** versioning-of-docs · **Severity:** Medium · **Mechanical:** False

**Evidence:** Roughly 40 runs across four layers, asking not "does the guard exist" but "does
it run":

**Suggested fix:** Pin this measurement to a checked-date or the commit hash of the runs it summarizes.

### `docs/plugin-rebuild-findings.md:33` — Unpinned enforcement-inventory count ("19 rules enforced; behavior moved 1 case in 5")

**Dimension:** versioning-of-docs · **Severity:** Medium · **Mechanical:** False

**Evidence:** | rule as code that raises | 19 rules enforced; behavior moved 1 case in 5 |

**Suggested fix:** Pin this rule-count/ratio to a commit hash or checked-date.

### `docs/plugin-benchmark-plan.md:163` — Unpinned hook/enforcement inventory (line numbers and line-count citations for pretooluse_guard.py and other hook files)

**Dimension:** versioning-of-docs · **Severity:** Medium · **Mechanical:** False

**Evidence:** - `plugins/cupertino/hooks/pretooluse_guard.py` (338 lines) implements all four required properties directly:
  - **Exit-2 + hookEventName-carrying stdout JSON**: `deny()` (lines ~57-65) prints ...

**Suggested fix:** The whole 'Citations' section (lines 148-176) cites specific line numbers and line counts in hook files without any commit hash or checked-date pin anywhere in the document (the closest is the vague 'as of this checkout' at line 170). Add an explicit commit hash or checked-date for the section.

### `docs/plugin-benchmark-phase1-results.md:25` — Entire benchmark-results document has no commit/date pin for measured file/score counts

**Dimension:** versioning-of-docs · **Severity:** High · **Mechanical:** False

**Evidence:** | Plugin | n | min | median | max | Every file EXIT=1? | Verdict |
|---|---|---|---|---|---|---|
| andon | 8 | 0 | 1 | 4 | No (4 tribunal agents = 0) | **FAIL** |
| confab | 7 | 2 | 2 | 4 | No (3 files = 0) | **FAIL** |

**Suggested fix:** Add a commit hash or checked-date to the document header (or per-table) stating which checkout of werkstoff/prp/code-modernization/superpowers these per-file scores and counts were measured against — none currently exists in this file.

### `docs/plugin-benchmark-phase1-results.md:84` — Unpinned third-party plugin score inventory (code-modernization, superpowers, Wirasm/prp)

**Dimension:** versioning-of-docs · **Severity:** Medium · **Mechanical:** False

**Evidence:** | Wirasm/prp @ `development` | single unit | 10 | 1 | 2.5 | 4 |
| code-modernization (anthropics/claude-plugins-official) | single unit | 16 | 1 | 2 | 3 |
| obra/superpowers @ `main` | single unit | 18 | 0 | 1 | 3 |

**Suggested fix:** Pin these third-party repo score counts to the commit/checked-date of the shallow clone they were scored from (the document says 'fresh shallow clones' but never records which commit).

### `docs/plugin-benchmark-phase2-results.md:12` — Entire executed-chain benchmark document has no commit/date pin for measured pass/fail results

**Dimension:** versioning-of-docs · **Severity:** High · **Mechanical:** False

**Evidence:** | Plugin | Chain | Verdict |
|---|---|---|
| andon | AND-1 preflight → loop | FAILED |
| andon | AND-2 loop → verify | **WORKED** |

**Suggested fix:** Add a commit hash or checked-date the werkstoff plugins were at when these chains were executed — the document currently has no such pin anywhere.
