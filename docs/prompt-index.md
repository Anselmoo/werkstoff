# Prompt index by plugin

Every example prompt shipped by the 9 plugin READMEs, 79 in
total, collected on one page. This is the plugin-indexed view; for the task-indexed
view — which skill fires at which moment of a piece of work — see the
[prompt catalog](/catalog/).

This page is generated from the plugin READMEs by
`tools/prompt-index/build_prompt_index.py` and tracked as an artifact, so it
cannot drift from them. Edit the prompts in their own README, never here.

## andon

[`plugins/andon/README.md`](https://github.com/Anselmoo/werkstoff/blob/main/plugins/andon/README.md) — 6 prompts.

### Check readiness first

````prompt
"run andon-preflight against this repo"
````

> Triggers `andon-preflight` — read-only readiness report (stage legibility, ledger writability, house-rules presence); never creates the ledger.

### Start hardening

````prompt
"harden this repo, one gap at a time"
````

> Triggers `andon-loop` — detects the value stream, proposes and verifies a fix for the current stage's gap, and halts rather than advancing past a broken or unproven wire.

### Check the board

````prompt
"what does the andon board look like right now"
````

> Triggers `andon-status` — read-only: stream table, cursor, pass/cycle counters, open gap counts; nothing advances.

### Propose a fix

````prompt
"propose a fix for this gap, only ask where it actually matters"
````

> Triggers `andon-propose` — proposes maximally from the ledger/codebase/house-rules, then grills you one question at a time, only on genuinely load-bearing forks.

### Prove a wire

````prompt
"prove this wire is actually proven"
````

> Triggers `andon-verify` — routes the wire to one of seven evidence-grounded strategies and returns a structured green/red verdict.

### Resume a paused pass

````prompt
"resume the andon ledger from where we left off"
````

> Triggers `andon-loop` — continues an existing ledger's cycle rather than starting fresh, still refusing to advance past whatever gap stopped the last pass.

## cli-scaffold

[`plugins/cli-scaffold/README.md`](https://github.com/Anselmoo/werkstoff/blob/main/plugins/cli-scaffold/README.md) — 5 prompts.

### Use the slash command directly

````prompt
/cli-scaffold rust called myapp
````

> The slash command itself — skips straight to generation for a named language and app name.

### Ask in plain language

````prompt
"scaffold a Python CLI named foo that fetches weather data"
````

> Triggers `scaffold-cli` (interpreted paradigm) — natural-language equivalent of the slash command: resolves the language, loads the doctrine, generates, then verifies.

### Scaffold a shell CLI

````prompt
"scaffold a bash CLI called backup-tool"
````

> Triggers `scaffold-cli` (shell paradigm, `cli-scaffold-shell`) — same five-pillar doctrine, plus POSIX-sh bashism checks.

### Scaffold a compiled-language CLI

````prompt
"scaffold a CLI in Go called deploy-bot"
````

> Triggers `scaffold-cli` (compiled paradigm, `cli-scaffold-compiled`) — produces a lib+binary split with zero CLI-framework imports in the core library, packaging metadata for Go's idiomatic channel, and a `--help` snapshot test.

### An unsupported or ambiguous language is refused, not guessed

````prompt
"scaffold a CLI in some scripting language, whatever's easiest"
````

> `scaffold-cli` refuses outright and lists the 12 supported languages rather than picking one for you — ambiguity is never silently resolved.

## codebase-consistency

[`plugins/codebase-consistency/README.md`](https://github.com/Anselmoo/werkstoff/blob/main/plugins/codebase-consistency/README.md) — 8 prompts.

### Check readiness first

````prompt
"is this area ready for a consistency pass?"
````

> Triggers `consistency-preflight` — read-only readiness report (stack detection, tooling, test-suite baseline, documented-convention inventory, scope check).

### Find the divergence

````prompt
"find the undocumented style/pattern inconsistencies in billing"
````

> Triggers `consistency-scan` — inventories undocumented, non-deprecated divergence per dimension, actively filtering out documented conventions and version-deprecated idioms.

### See it as a matrix

````prompt
"show me the consistency matrix for billing"
````

> Triggers `consistency-map` — renders the scan as a module × dimension heatmap (`matrix.json` + an interactive `CONSISTENCY_MATRIX.html`).

### Derive the canon

````prompt
"decide which pattern should be the canonical one, with provenance"
````

> Triggers `consistency-canonize` — weighs frequency, git-history maturity, and adoption recency per dimension, tagging each pick `documented` / `derived-majority` / `synthesized-new` / `needs-human-decision` rather than forcing a tie.

### Get the approval-ready plan

````prompt
"write up the alignment brief for billing so I can approve it"
````

> Triggers `consistency-brief` — synthesizes discovery into a phased, dependency-first plan with worked before/after examples; enters plan mode as a human approval gate.

### Apply it

````prompt
"align billing to the approved error-handling-style canon"
````

> Triggers `consistency-align` — applies the canon in place, one pilot module first, then the rest in dependency-aware escalating batches behind a circuit breaker.

### Prove nothing broke

````prompt
"verify the error-handling-style alignment on billing"
````

> Triggers `consistency-verify` — test-suite equivalence (or structural-diff fallback) plus a docs re-sync check, independently re-derived by a second adversarial pass.

### Check progress

````prompt
"where does the billing consistency pass stand?"
````

> Triggers `consistency-status` — read-only artifact inventory, staleness flags, and the single most useful next command.

## compass

[`plugins/compass/README.md`](https://github.com/Anselmoo/werkstoff/blob/main/plugins/compass/README.md) — 14 prompts.

### Run the full pipeline

````prompt
"help me think through this, it's complex and I'm not sure of the right approach"
````

> Triggers `compass-solve` — runs the full Clarify → Explore → Decompose → Execute → Revise pipeline.

### Explore before committing

````prompt
"before we commit to an approach, explore a few different ones"
````

> Triggers `compass-explore-branches` — proposes and scores multiple viable approaches instead of anchoring on the first.

### Clarify a fuzzy scope

````prompt
"the scope of this request is fuzzy, help me pin it down first"
````

> Triggers `compass-clarify-scope` — surfaces ambiguous phrasing and unstated success criteria before any work starts.

### Break a problem into stages

````prompt
"break this into steps — what depends on what"
````

> Triggers `compass-decompose-chain` — splits the problem into a 2-5 stage pipeline with explicit input/output contracts per stage, and derives which stages can run in parallel from the dependency graph.

### Score and fix a draft

````prompt
"score this draft against these criteria and fix what's weak"
````

> Triggers `compass-draft-revise` — rates 1-5 against each criterion, revises only what falls at or below threshold, and reports exactly what changed (capped at 2 revision cycles).

### Ground every claim

````prompt
"don't make this up — ground every claim in the actual code or docs"
````

> Triggers `compass-ground-evidence` — requires a file:line, URL, or explicitly-flagged prior knowledge behind every factual claim, and refuses to assert anything unverified.

### Investigate step by step

````prompt
"I don't know where the problem is — go find it"
````

> Triggers `compass-investigate-dynamically` — runs a Reasoning/Action/Observation loop where each observation decides the next step, for cases where the sequence of actions can't be planned upfront.

### Trace a multi-hop chain

````prompt
"trace how A affects D through the whole dependency chain"
````

> Triggers `compass-map-relationships` — extracts indexed relationship triples and traverses them hop by hop, citing the triple index at every hop.

### Combine the best of two approaches

````prompt
"the winner's good, but can we fold in what I liked from the runner-up?"
````

> Triggers `compass-negotiate-tradeoffs` — synthesizes a hybrid from 2-3 already-scored branches, but only presents it if it actually beats every source branch on at least one axis.

### Tune a reusable prompt

````prompt
"find the best wording for this system prompt — I have test cases"
````

> Triggers `compass-optimize-instruction` — generates one candidate per APE framing, scores each against your real test cases, and critiques the winner. Needs representative test cases; not for one-off prompts.

### Guard against a silent reasoning error

````prompt
"walk through this calculation carefully, I can't afford a wrong assumption here"
````

> Triggers `compass-reason-verify` — climbs a 4-rung ladder (zero-shot → Chain-of-Thought → self-consistency → PAL) matched to the actual failure-mode risk, applying Multimodal-CoT first if there's an image or diagram involved.

### Anchor a fuzzy output format

````prompt
"I can't describe the format, but here's an example — make it look like this"
````

> Triggers `compass-calibrate-format` — anchors the target shape to 2-5 concrete input/output examples instead of more prose, enforcing at least one near-boundary example so the set actually pins the decision.

### Write up a finished run

````prompt
"summarize what we just did for the PR"
````

> Triggers `compass-summarize-trace` — produces a fixed 7-section record (asked, assumed, weighed, run, produced, revised, not done) after a `compass-solve` pipeline finishes.

### Check one blocking assumption

````prompt
"before we rely on this, verify it's actually true"
````

> Triggers `compass-verify-assumptions` — checks exactly one named assumption against real evidence in at most 3 steps; for more than one uncertainty, invoke it once per uncertainty.

## confab

[`plugins/confab/README.md`](https://github.com/Anselmoo/werkstoff/blob/main/plugins/confab/README.md) — 8 prompts.

### Check for hallucinated dependencies

````prompt
"check if any of our dependencies are hallucinated"
````

> Triggers `confab-dependency-audit` — flags package names that don't exist in the real registry, independently re-verified before being reported.

### Check test strength

````prompt
"would our tests actually catch a bug here?"
````

> Triggers `confab-assertion-audit` — mutation-testing pass checking whether tests assert anything meaningful, not just execute the code.

### Run the full cycle

````prompt
"run the confab cycle on this repo"
````

> Triggers `confab-cycle` — bounded self-optimization loop: re-runs all four audits pass by pass, optionally applying fixes, until convergence.

### Check status

````prompt
"where does confab stand on this repo"
````

> Triggers `confab-status` — read-only dashboard: what's run, what's stale, what to run next.

### Check for contract drift

````prompt
"check if our type signatures and docstrings still match how the code is actually called"
````

> Triggers `confab-contract-drift` — compares type hints, docstrings, and API/OpenAPI/GraphQL schemas against real call-site or handler usage, independently re-verified by default.

### Audit the plugin's own agent design

````prompt
"is our own agent design safe — any unbounded retries or missing escalation paths?"
````

> Triggers `confab-agentic-reliability` — audits this repo's own skill/agent/workflow definitions for unbounded retry loops, unwired Find/Verify phases, and excessive tool grants.

### Quick pre-commit check

````prompt
"is this diff okay to commit?"
````

> Triggers `confab-code-change` — runs only the domains whose file patterns match what actually changed, and always produces an advisory verdict that never blocks the commit.

### Check readiness first

````prompt
"is confab set up correctly in this repo?"
````

> Triggers `confab-preflight` — five independent readiness checks, one verdict per domain skill, before any audit actually runs.

## cupertino

[`plugins/cupertino/README.md`](https://github.com/Anselmoo/werkstoff/blob/main/plugins/cupertino/README.md) — 15 prompts.

### Run the full review

````prompt
"run the full cupertino review on this feature"
````

> Triggers `cupertino-review` — runs all eight lifecycle stages end-to-end, backwards-compatibility check through reveal.

### Convene the council

````prompt
"convene the cupertino council on this design"
````

> Triggers `cupertino-council` — five-lens review (Reduction, Craft, Hierarchy, Usability, Metaphor), tensions resolved in a fixed precedence order.

### Check against the handbook

````prompt
"check this codebase against our design handbook"
````

> Triggers `cupertino-handbook-check` — flags drift from an already-drafted handbook rule, with file:line evidence.

### Start from the experience, not the tech

````prompt
"we need a feature that lets users share a project with a client — nothing's decided yet"
````

> Triggers `cupertino-backwards` — a pre-architecture gate: establishes what experience actually matters before any database, framework, or API gets named. Always runs first; every other lifecycle stage stays locked until it has.

### Cut a sprawling portfolio down

````prompt
"we have twelve pricing tiers and nobody can explain the difference — help us cut"
````

> Triggers `cupertino-focus` — runs right after `cupertino-backwards`, reducing shipped and planned variants to the smallest focused set before architecture work commits effort.

### Transfigure a boring feature

````prompt
"nobody uses our export feature, it's just a chore — can we make it delightful?"
````

> Triggers `cupertino-elevate` — only for a commodity feature already in scope for the current build (error messages, logs, settings, onboarding...); never seeks one out on its own.

### Consider replacing your own best thing

````prompt
"is it time to replace our own flagship feature with something better we'd build today?"
````

> Triggers `cupertino-cannibalize` — user-invoked only, never automatic; a deliberate post-ship check on whether to cannibalize a currently-successful, load-bearing thing.

### Decide build vs. buy for one seam

````prompt
"should we build our own auth system or just integrate an existing provider?"
````

> Triggers `cupertino-integrate` — judges one specific, named boundary at a time; never applied as a blanket build-vs-buy policy across a whole system.

### Check whether an architecture will age well

````prompt
"will this API design still make sense in two years, or are we setting up a rewrite?"
````

> Triggers `cupertino-longevity` — evaluates whether the architecture can evolve incrementally or is quietly committing to a future rewrite; pairs with `cupertino-integrate` at architecture-decision time.

### Spike an uncertain approach

````prompt
"I'm not sure this library can actually do what we need — let's just build a throwaway spike"
````

> Triggers `cupertino-prototype` — settles one specific empirical uncertainty by building and running a small experiment, not by debating it further.

### Get the "one more thing"

````prompt
"is there anything else this needs before we ship it?"
````

> Triggers `cupertino-reveal` — the final ship-time stage: delivers exactly one non-obvious, high-leverage addition, built rather than pitched — never a list.

### Redesign the first five minutes

````prompt
"our onboarding flow feels clunky — help us fix the first-run experience"
````

> Triggers `cupertino-unbox` — scoped strictly to a new user's first five minutes (install, first-run, onboarding), distinct from `cupertino-elevate`'s ongoing-feel transfiguration.

### Draft a durable handbook

````prompt
"write us a design handbook that captures our actual conventions"
````

> Triggers `cupertino-handbook-draft` — persists one checkable rule per dimension for a domain (design, code, testing, or docs), honestly labeling scaffolded defaults where no real convention exists yet.

### Pull in just the relevant handbook rules

````prompt
"what does our handbook say that's relevant to this task?"
````

> Triggers `cupertino-handbook-apply` — surfaces only the constraints and exceptions relevant to the upcoming task, not the whole document.

### Apply the mechanical handbook fixes

````prompt
"fix the mechanical findings from the last handbook check"
````

> Triggers `cupertino-handbook-fix` — only after fix mode is explicitly enabled for a domain; never touches a `mechanical:false` finding, and never infers consent from a check report alone.

## lehre

[`plugins/lehre/README.md`](https://github.com/Anselmoo/werkstoff/blob/main/plugins/lehre/README.md) — 5 prompts.

### Start a new project so it cannot drift

````prompt
"I'm starting a CLI that ingests CSV from three vendors and writes Parquet. Set it up
properly — I don't want the usual mess where everything imports everything."
````

### Establish and enforce a doctrine on an existing repo

````prompt
"research what rules this codebase should follow for its stack, check them against what
we actually do, and make the important ones actually enforced"
````

### Find where the code violates its own architecture

````prompt
"where do we violate our own layering, and which of those are real"
````

### Make the rules survive without the plugin

````prompt
"pin these rules into CI so they still hold when nobody's running Claude"
````

### Ask what is currently blocked

````prompt
"lehre status — what can I build next?"
````

## self-assess

[`plugins/self-assess/README.md`](https://github.com/Anselmoo/werkstoff/blob/main/plugins/self-assess/README.md) — 16 prompts.

### Map the architecture

````prompt
"map this repo's architecture"
````

> Triggers `self-assess-stage-map` — import-graph-based stage/wire detection, not naive directory guessing.

### Run the auto-pilot

````prompt
"run the auto-pilot"
````

> Triggers `self-assess-autopilot` — full check → plan → gate → fix/validate, gated behind explicit settings before anything is written.

### Check status

````prompt
"where does self-assess stand"
````

> Triggers `self-assess-status` — read-only board of what's been run and what's stale.

### Sweep a portfolio

````prompt
"sweep our whole portfolio of repos"
````

> Triggers `self-assess-portfolio` — multi-repo dashboard, graded worst-signal-wins.

### Check readiness first

````prompt
"can self-assess actually analyze this codebase?"
````

> Triggers `self-assess-preflight` — verifies language detection, tool availability, house-rules presence, and git/CI presence, then assigns a Ready/Ready-with-gaps/ Not-ready verdict per downstream skill.

### Find architecture problems

````prompt
"find god-modules or dependency cycles in this codebase"
````

> Triggers `self-assess-arch-health` — reads the stage graph from `self-assess-stage-map` and confirms every candidate god-module or cycle against actual code, not just the graph.

### Audit git/CI setup

````prompt
"check our git remotes and CI setup for redundant mirrors"
````

> Triggers `self-assess-ci-topology` — audits remote topology and CI config for redundancy and mirror risk, masking every credential to a short preview.

### Find modernization opportunities

````prompt
"find deprecated idioms and code smells in this repo"
````

> Triggers `self-assess-code-idiom` — judges idioms against the actual language version declared in the repo's own manifest, never a fixed list, and separates fixable modernization from judgment-requiring smells.

### Score complexity per module

````prompt
"which module needs attention first? score complexity per stage"
````

> Triggers `self-assess-complexity-score` — computes a relative complexity index (2.94 × KSLOC^1.10) per stage, and lists unmeasured stages plainly rather than inventing numbers.

### Check documentation accuracy

````prompt
"does our README still match what the code actually does?"
````

> Triggers `self-assess-docs-drift` — extracts falsifiable claims from CLAUDE.md/README/ADRs and verifies each one against the cited code.

### Mine the hidden business rules

````prompt
"document the domain rules hidden in this code as testable specs"
````

> Triggers `self-assess-extract-rules` — mines calculations, validations, and state transitions into Given/When/Then rules, looping to convergence and requiring a two-judge panel to confirm any P0 rule.

### Apply the modernization findings

````prompt
"apply the modernization findings self-assess-code-idiom found"
````

> Triggers `self-assess-idiom-fix` — applies only eligible modernization-category findings, gated behind `idiom_fix.mode: fix`, one remediator dispatch per (file, kind) cluster, then hands off to `andon-verify` unverified.

### Check our own conventions

````prompt
"audit this code against our house rules"
````

> Triggers `self-assess-lint-audit` — extracts discrete rules from `.claude/house-rules.md` (or CLAUDE.md as a fallback) and verifies violations, capped at `lint_max_rules` dispatches.

### Turn findings into a plan

````prompt
"synthesize all the findings into a modernization brief"
````

> Triggers `self-assess-transform-brief` — synthesizes stage-map, arch-health, and every other domain summary into a phased, ranked, read-only transformation plan.

### Execute one authorized phase

````prompt
"execute phase 3 from the modernization brief"
````

> Triggers `self-assess-transform-execute` — applies exactly one human-authorized phase, gated behind `transform.mode: execute`, a clean tree, and every Open Question resolved.

### Audit UI accessibility

````prompt
"check our components for accessibility issues and hardcoded design values"
````

> Triggers `self-assess-ui-audit` — statically audits JSX/TSX, Vue/Svelte, HTML, and CSS/SCSS for accessibility and design-token problems, never running or rendering the app.

## takt

[`plugins/takt/README.md`](https://github.com/Anselmoo/werkstoff/blob/main/plugins/takt/README.md) — 2 prompts.

### Declare the beats for a repository

````prompt
"set up takt so UI code can't be written before the design council has run"
````

> Writes a `.claude/takt.local.md` beat with the UI globs and a `require` marker, after which the hook refuses a matching edit until that marker exists.

### Understand a refusal

````prompt
"takt just blocked my edit — what beat am I running ahead of?"
````

> The denial names the beat id, the reason, and the missing marker; the escape hatch is `TAKT_DISABLE_GUARD=1` when the order genuinely does not apply.
