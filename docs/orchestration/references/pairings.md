---
pairings:
  - id: "brainstorming-cli-architecture"
    skillA: "superpowers:brainstorming"
    skillB: "cli-scaffold:cli-architecture"
    source: "superpowers"
    beat: "inspect"
    why: "A CLI scaffolded from an unexamined idea encodes the idea's flaws structurally, and a scaffold that violates the doctrine is cheaper to regenerate than to retrofit -- so both gates have to close before any generator runs."
    how: "brainstorming runs first, before any code exists, to work out what the CLI should actually do. cli-architecture then loads next on its own instruction -- \"BEFORE any paradigm skill (cli-scaffold-compiled, cli-scaffold-interpreted, cli-scaffold-shell) generates a scaffold\" -- so the language-specific paradigm skill never runs until both gates have closed."
    prompt: "I want to build a small CLI for this. Let's brainstorm what it should do before any code exists."
    dos:
      - "Load cli-architecture before the paradigm skill runs, every time -- it states this about itself."
      - "Treat paradigm choice (compiled/interpreted/shell) as fixed by language once picked."
    donts:
      - "Don't swap paradigm after generation -- it \"cannot be swapped later without regenerating.\""
      - "Don't let the paradigm skill run first and retrofit the doctrine onto an existing scaffold."
    grounding: "tools/werkstoff-cli/ already matches this shape -- a src/werkstoff/ package split into cli.py and core.py, snapshot tests under tests/__snapshots__/, and a pyproject.toml pinning requires-python = \">=3.12\"."
    recipeTask: "Scaffold a new project or CLI"
    recipeUrl: "/catalog/before-any-code/scaffold-new-project-or-cli"

  - id: "business-rules-extractor-self-assess-extract-rules"
    skillA: "code-modernization:business-rules-extractor"
    skillB: "self-assess:self-assess-extract-rules"
    source: "claude-plugins-official"
    beat: "inspect"
    why: "Two independently-authored extractors emitting the same Given/When/Then shape make disagreement between them signal, not noise -- a single extractor's output is not something you can cross-check against itself."
    how: "self-assess-extract-rules mines rules from the executable code first, loops to convergence, and requires a two-judge panel for any P0-rated rule. code-modernization:business-rules-extractor runs second, as an independent second read with the same output shape -- run after the first extractor so it's a cross-check, not an anchor."
    prompt: "extract this codebase's real business rules as Given/When/Then specs, from the executable code, not from comments or docs"
    dos:
      - "Run the second extractor after the first, specifically so it can disagree with it, not repeat it."
      - "Feed business-rules-extractor's output to BUSINESS_RULES.md only when /modernize-brief is the pipeline actually being signed."
    donts:
      - "Don't run both over the same modules expecting them to reconcile -- routing.md is explicit: running both produces two rule sets that will not be reconciled by anything. Choose by which brief, if any, is going to be signed."
      - "Don't treat the second pass as a rerun of the first -- it feeds a different consumer (a repo's own understanding of itself, not BUSINESS_RULES.md)."
    grounding: "This is the exact scope overlap docs/orchestration/references/routing.md governs (\"Same extraction, different consumer\"); the catalog recipe itself notes this dispatches code-modernization leaves directly and must not run alongside a signed /modernize-* brief."
    recipeTask: "Specify an inherited codebase's business rules"
    recipeUrl: "/catalog/before-any-code/specify-inherited-business-rules"

  - id: "version-delta-analyst-self-assess-code-idiom"
    skillA: "code-modernization:version-delta-analyst"
    skillB: "self-assess:self-assess-code-idiom"
    source: "claude-plugins-official"
    beat: "inspect"
    why: "A same-stack uplift preserves code and tweaks it; version-delta-analyst finds which breaking changes actually bite this codebase, and self-assess-code-idiom then judges the result against the version the repo actually targets -- not the newest one."
    how: "version-delta-analyst is dispatched directly, standalone, sanctioned by modernize-brief.md itself rather than through the eight-stage pipeline: when the delta catalog is missing, spawn the version-delta-analyst agent directly, then return -- do not guess at the deltas. self-assess-code-idiom then runs against the manifest-declared version, and self-assess-idiom-fix applies only the mechanical fixes afterward."
    prompt: "we're moving this codebase up a major version of the same stack. Which breaking changes actually affect our code?"
    dos:
      - "Dispatch version-delta-analyst as a standalone leaf when you only need the deltas, not the whole /modernize-uplift pipeline."
      - "Judge idioms against the version the manifest already declares -- not the newest available version."
    donts:
      - "Don't reach for self-assess-code-idiom to plan the uplift itself -- routing.md: it judges idioms against the language version the repo's manifest already declares, so it cannot plan a move to a version the manifest has not reached."
      - "Don't run the idiom audit before the uplift -- running the auditor before the uplift measures the old world, not the new one."
    grounding: "This exact pairing is one of orchestration/README.md's three worked examples -- \"code-modernization, at the 'Inspect and research' beat.\""
    recipeTask: "Perform a same-stack version uplift"
    recipeUrl: "/catalog/change-existing-code/same-stack-version-uplift"

  - id: "compass-investigate-dynamically-systematic-debugging"
    skillA: "compass:compass-investigate-dynamically"
    skillB: "superpowers:systematic-debugging"
    source: "superpowers"
    beat: "inspect"
    why: "The reported behavior's location is unknown, and a pre-planned file list cannot adapt to what each observation reveals -- so the search has to run before the debugging discipline that assumes a location already."
    how: "compass-investigate-dynamically finds where the behavior actually lives first. superpowers:systematic-debugging then works the located behavior to root cause, mandatory before any fix is proposed."
    prompt: "I don't know where this behavior is implemented -- go find it before we talk about fixing it"
    dos:
      - "Let the search adapt to each observation rather than following a plan written before any file was opened."
      - "Work to root cause before proposing any fix -- no fix, no patch, no workaround until the cause is proven."
    donts:
      - "Don't propose a fix before the cause is nailed down -- a fix without a cause is a guess with a diff."
      - "Don't reuse a pre-planned file list once the first observation contradicts it."
    grounding: "the failure mode recorded in .github/workflows/plugin-checks.yml: a .gitignore regression that silently drops a vendored file, a bug whose symptom appears months later at a hook denial rather than where the cause lives."
    recipeTask: "Root-cause a bugfix from a tracked issue"
    recipeUrl: "/catalog/defect-work/root-cause-bugfix-from-tracked-issue"

  - id: "compass-negotiate-tradeoffs-writing-plans"
    skillA: "compass:compass-negotiate-tradeoffs"
    skillB: "superpowers:writing-plans"
    source: "superpowers"
    beat: "split"
    why: "A scope that never becomes a written plan is re-litigated at every subsequent step, and a hybrid approach negotiated between branches is only checkable while both source branches are still scored and live."
    how: "compass-explore-branches scores genuinely distinct readings of the request, compass-negotiate-tradeoffs settles any fork those branches can't resolve on their own, and superpowers:writing-plans turns the settled scope into a written plan with steps before anyone touches code."
    prompt: "we've agreed the scope -- turn it into a written plan with steps before touching code"
    dos:
      - "Settle the tradeoff while both branches are still live and scored, not after one has already been picked."
      - "Turn the settled scope into a written plan immediately -- before implementation starts."
    donts:
      - "Don't let an ambiguous scope go straight to a plan without scoring alternatives first -- scoring alternatives after one has been built anchors on the built one."
      - "Don't leave a settled scope unwritten -- it gets re-litigated at every later step."
    grounding: "\"make the plugins consistent\" splits on a documented boundary: plugins/codebase-consistency/README.md lines 28-47, headed \"Scope -- read this before installing both this and self-assess\", route two categories of finding out to self-assess by name."
    recipeTask: "Scope an ambiguous task"
    recipeUrl: "/catalog/before-any-code/scope-ambiguous-task"

  - id: "compass-decompose-chain-systematic-debugging"
    skillA: "compass:compass-decompose-chain"
    skillB: "superpowers:systematic-debugging"
    source: "superpowers"
    beat: "split"
    why: "Several jobs red at once can mean one cause with many symptoms, or several independent causes -- chasing symptoms before telling those two cases apart wastes the whole first pass."
    how: "self-assess-ci-topology audits the CI config itself first, since a config-level defect explains all the symptoms at once. compass-decompose-chain then derives which of the red jobs are genuinely independent tracks from the dependency graph, not by guess, before superpowers:systematic-debugging works any single failure to root cause."
    prompt: "work the lint failure to root cause first -- no fixes proposed until the cause is nailed down"
    dos:
      - "Derive independent tracks from the actual dependency graph before splitting the work, not from how the jobs happen to be laid out."
      - "Work each track to root cause before proposing any fix."
    donts:
      - "Don't debug the first red job you see without first checking whether a single config-level cause explains all of them."
      - "Don't propose a fix ahead of a root cause -- a fix proposed ahead of a root cause is a second failure mode."
    grounding: "plugin-checks.yml runs eleven checks with continue-on-error: true and collapses them into one \"Fail the job if any check failed\" step, so one red job can mean any of eleven independent causes."
    recipeTask: "Diagnose a pipeline red across several jobs"
    recipeUrl: "/catalog/ci-release/pipeline-red-across-jobs"

  - id: "dispatching-parallel-agents-andon-verify"
    skillA: "superpowers:dispatching-parallel-agents"
    skillB: "andon:andon-verify"
    source: "superpowers"
    beat: "execute"
    why: "What can run in parallel has to come from the dependency graph, not from how the plan happens to be laid out, and a partial parallel result reads exactly like a complete one until something checks each wire on its own."
    how: "compass-decompose-chain derives which workstreams are genuinely independent. superpowers:dispatching-parallel-agents and subagent-driven-development then execute them -- multiple dispatch calls in one response is parallel execution, one per response is sequential -- and andon:andon-verify proves each workstream on its own rather than the aggregate result inheriting one shared verdict."
    prompt: "break this plan into independent workstreams -- tell me what actually depends on what and what can truly run in parallel"
    dos:
      - "Send every parallel dispatch in the SAME response -- one call per response runs sequentially regardless of intent."
      - "Always specify the model explicitly per dispatch -- an omitted model silently inherits the session's, usually the most expensive, tier."
      - "Give each workstream its own andon-verify proof."
    donts:
      - "Don't split work that shares state -- two agents editing the same file interfere regardless of how cleanly the split looked on paper."
      - "Don't let a workstream that waits on another's output masquerade as parallel -- it's a sequential step wearing a parallel label."
    grounding: "One of orchestration/README.md's three worked examples, quoted unedited; plugins/takt/hooks/hooks.json is the PreToolUse hook (not a skill) that denies a dispatch running ahead of its declared beat in this same recipe."
    recipeTask: "Execute a written plan across parallel workstreams"
    recipeUrl: "/catalog/change-existing-code/execute-plan-across-parallel-workstreams"

  - id: "cupertino-council-frontend-design"
    skillA: "cupertino:cupertino-council"
    skillB: "frontend-design:frontend-design"
    source: "claude-plugins-official"
    beat: "execute"
    why: "Design work has a hard ordering constraint most tasks don't: the principled pass must precede the code. cupertino-council's own frontmatter states it directly -- \"Always run before code, never after -- retrofitting the council onto finished code defeats the purpose.\""
    how: "cupertino-council convenes its five-voice design review before a single line of markup exists. frontend-design then implements the design that was settled -- after the principles are settled, not in place of settling them."
    prompt: "design this screen from first principles before we write any markup -- I don't want something that just looks like every other AI-built page"
    dos:
      - "Run cupertino-council before any markup exists, every time -- it's a pre-code gate by its own declaration."
      - "Hand frontend-design the settled design, not an open brief -- implementation follows the principles, it doesn't set them."
    donts:
      - "Don't retrofit the council onto a finished screen -- \"retrofitting the council onto finished code defeats the purpose\" is the plugin's own stated rule."
      - "Don't skip straight to frontend-design on an interface that hasn't had a principled pass yet."
    grounding: "checked against the shared token set in tools/design-tokens/tokens.css, and the HTML surfaces this repo already ships: the andon board viewer and the branch-comparison viewer."
    recipeTask: "Do UI and design-system work"
    recipeUrl: "/catalog/surface/ui-and-design-system-work"

  - id: "frontend-design-self-assess-ui-audit"
    skillA: "frontend-design:frontend-design"
    skillB: "self-assess:self-assess-ui-audit"
    source: "claude-plugins-official"
    beat: "verify"
    why: "Accessibility, semantic markup, and hardcoded design values are only checkable once the markup actually exists -- running the audit before the build produces nothing to audit."
    how: "frontend-design implements the settled design first. self-assess-ui-audit then statically audits the built surface -- JSX/TSX, Vue/Svelte, HTML, CSS/SCSS -- for accessibility and hardcoded values, without ever running the app."
    prompt: "audit the UI we just built for accessibility, semantic markup, and hardcoded design values -- statically, don't run the app"
    dos:
      - "Run the audit only after real markup exists -- it's genuinely post-hoc."
      - "Keep the audit static -- read source, never execute or render the app."
    donts:
      - "Don't run self-assess-ui-audit against a design that's still principles-only -- there's no markup yet to check."
      - "Don't substitute a live-app check for the static read; the skill's own scope is explicitly static-only."
    grounding: "the andon board viewer (plugins/andon/scripts/build_board_html.py) and the branch-comparison viewer (plugins/compass/scripts/build_branch_comparison_html.py), checked against tools/design-tokens/tokens.css."
    recipeTask: "Do UI and design-system work"
    recipeUrl: "/catalog/surface/ui-and-design-system-work"

  - id: "code-simplifier-codebase-consistency"
    skillA: "pr-review-toolkit:code-simplifier"
    skillB: "codebase-consistency:pattern-extractor"
    source: "claude-plugins-official"
    beat: "verify"
    why: "Documented rules and undocumented-but-real patterns are audited by different plugins on purpose, and simplifying before the convention is settled means simplifying twice."
    how: "self-assess audits the documented half first (self-assess-lint-audit, then convention-auditor). codebase-consistency:pattern-extractor then handles the undocumented half, refusing to force a pick when competing variants are genuinely tied, and consistency-critic re-derives the verdict as a second judge. pr-review-toolkit:code-simplifier runs last, deliberately, on the now-aligned code only."
    prompt: "extract the discrete, checkable rules this repo's own documentation states, and audit the code against them"
    dos:
      - "Run code-simplifier last, after both the documented and undocumented halves have settled -- not before."
      - "Let consistency-critic re-derive pattern-extractor's verdict rather than rubber-stamping it."
    donts:
      - "Don't simplify before the convention is canonized -- the code you'd simplify may get rewritten to the canonical form immediately after."
      - "Don't blur the documented/undocumented boundary -- codebase-consistency's own README routes documented conventions out to self-assess by name; running both for the same finding double-reports it."
    grounding: "One of orchestration/README.md's three worked examples; plugins/codebase-consistency/README.md's own \"Scope\" section is what draws the boundary."
    recipeTask: "Audit a repo against its own documented conventions"
    recipeUrl: "/catalog/quality-verification/audit-against-documented-conventions"

  - id: "hook-development-cupertino-handbook-check"
    skillA: "plugin-dev:hook-development"
    skillB: "cupertino:cupertino-handbook-check"
    source: "claude-plugins-official"
    beat: "verify"
    why: "A rule that lives only in prose is a suggestion. This repo measured the difference: prose in a SKILL.md is baseline, a fenced python3 guard fires one run in three, a Workflow-script guard fires one run in fourteen, and a PreToolUse hook of type \"command\" blocks on the first attempt."
    how: "cupertino-handbook-draft turns the convention into one concrete, file:line-grounded rule. cupertino-handbook-check then runs that rule against real files to find every divergence before any enforcement is written -- enforcement written before the divergence is known will either block everything or nothing. plugin-dev:hook-development then writes the PreToolUse hook, since prose alone won't hold."
    prompt: "prose isn't holding this. Write a PreToolUse hook that blocks it on the first attempt."
    dos:
      - "Measure divergence with cupertino-handbook-check before writing the hook -- enforcing an unmeasured rule blocks everything or nothing."
      - "Use type: \"command\" for the hook -- a \"prompt\" hook asks a model to decide, which is exactly the unreliable rung this pairing exists to skip past."
      - "Make the deny emit both exit 2 with the reason on stderr AND stdout JSON carrying hookEventName and permissionDecisionReason."
      - "Fail closed, with a named escape hatch."
    donts:
      - "Don't write the hook before the check step has run -- you'd be enforcing a rule against divergence you haven't measured."
      - "Don't settle for a \"prompt\"-type hook and call it enforcement; only type: \"command\" measured as reliably blocking on this repo's own runs."
    grounding: "tools/enforcement-audit/rules/ currently holds a single andon.json; six plugins have no rules file at all -- this repo's own CLAUDE.md records the enforcement ladder this pairing is built on."
    recipeTask: "Make a strategy enforced rather than documented"
    recipeUrl: "/catalog/quality-verification/make-strategy-enforced-not-documented"

  - id: "type-design-analyzer-confab-contract-drift"
    skillA: "pr-review-toolkit:type-design-analyzer"
    skillB: "confab:confab-contract-drift"
    source: "claude-plugins-official"
    beat: "verify"
    why: "Changing what a function hands back is a contract change wearing a refactor's clothes -- every call site is a participant, and type hints, signatures, docstring params, and schemas drift apart precisely during a migration like this."
    how: "type-design-analyzer reviews the new type's design -- encapsulation, invariants, enforceability -- before N call sites adopt the shape, since that's cheapest to fix early. confab-contract-drift then checks, after the migration, whether the declared signatures still agree with how the code is actually called."
    prompt: "before we roll this new return type out everywhere, review its design -- encapsulation, invariants, whether it's actually enforceable"
    dos:
      - "Review the type's design before rollout, not after -- it's cheapest before N call sites depend on the shape."
      - "Dispatch both together when a diff touches types or signatures -- gates.md's own routing table pairs them for exactly that touch-category."
    donts:
      - "Don't treat a passing test suite as evidence of equivalence on its own -- a passing suite is evidence only if the suite would notice."
      - "Don't skip the contract-drift check just because the type review passed -- one rates design quality, the other checks whether call sites actually agree with it."
    grounding: "the core.py to cli.py boundary in tools/werkstoff-cli/src/werkstoff/, whose output shape is pinned by the snapshot file tests/__snapshots__/test_cli.ambr -- snapshots that re-record silently if the migration lands before they're read."
    recipeTask: "Migrate a return shape or type representation"
    recipeUrl: "/catalog/change-existing-code/migrate-return-shape-or-type"

  - id: "silent-failure-hunter-andon-verify"
    skillA: "pr-review-toolkit:silent-failure-hunter"
    skillB: "andon:andon-verify"
    source: "claude-plugins-official"
    beat: "verify"
    why: "The most expensive CI defect is the green one -- a job exits zero and the work it was supposed to do never happened. A green exit code is not evidence; the wire it claims to close has to be proven independently."
    how: "silent-failure-hunter hunts the job for swallowed errors, skipped branches, and fallbacks that hide the real outcome. andon-verify then proves the specific wire the job claims -- \"job ran -> artifact changed\" -- rather than accepting the exit code as evidence."
    prompt: "this job exits zero but nothing downstream changed -- go hunt for swallowed errors, skipped branches, and fallbacks that hide the real outcome"
    dos:
      - "Hunt the suppression first -- silent-failure-hunter is purpose-built for exactly this shape."
      - "State the wire's contract explicitly when dispatching andon-verify -- it routes among seven strategies by reading the wire's contract, and a dispatch with no stated contract has nothing to route against."
    donts:
      - "Don't accept a green exit code as proof the job did what it claims."
      - "Don't dispatch andon-verify with only a diff and no stated contract -- unlike the other reviewers in this catalog, it won't infer one."
    grounding: ".github/workflows/auto-version-bump.yml skips entirely when the head commit message doesn't start with a recognized conventional-commit type; its own header comment records that a plain-English PR title \"is silently skipped, by design.\""
    recipeTask: "Investigate a job that reports success but changed nothing"
    recipeUrl: "/catalog/ci-release/job-reports-success-but-changed-nothing"

  - id: "confab-assertion-audit-pr-test-analyzer"
    skillA: "confab:confab-assertion-audit"
    skillB: "pr-review-toolkit:pr-test-analyzer"
    source: "claude-plugins-official"
    beat: "verify"
    why: "A green suite proves the tests ran, not that they would notice -- coverage percentages are compatible with assertions that assert nothing."
    how: "confab-assertion-audit proposes plausible mutations (off-by-one, boundary flip, condition negation) to the target source and checks whether any existing test would catch them. pr-test-analyzer reviews the same tests for behavioral coverage gaps, not line-coverage percentage -- the two angles catch different shapes of the same failure."
    prompt: "mutate this module -- flip a boundary, negate a condition, shift an index -- and tell me which mutations the tests would not catch"
    dos:
      - "Run both -- mutation testing and behavioral-coverage review catch different shapes of a test suite that passes for the wrong reason."
      - "Watch for an assertion whose expected value brackets a hardcoded default, so the test passes whether or not the real logic ever executes."
    donts:
      - "Don't trust a green run, or a high coverage percentage, as evidence the suite would notice a real regression."
      - "Don't stop at line coverage -- pr-test-analyzer is explicitly scoped to behavioral coverage instead."
    grounding: "auditing plugins/confab/scripts/test_cycle_engine.py and tools/enforcement-audit/test_audit_enforcement.py for assertions whose expected value is the same hardcoded default the code falls back to when the real path never runs."
    recipeTask: "Investigate tests that pass while the code is broken"
    recipeUrl: "/catalog/defect-work/tests-pass-while-code-is-broken"

  - id: "self-assess-docs-drift-claude-md-improver"
    skillA: "self-assess:self-assess-docs-drift"
    skillB: "claude-md-management:claude-md-improver"
    source: "claude-plugins-official"
    beat: "inspect"
    why: "claude-md-improver's own \"Currency\" criterion grades a CLAUDE.md's freshness on a letter scale, not claim by claim -- extending a file whose existing claims are already wrong compounds the drift instead of fixing it."
    how: "self-assess-docs-drift reads CLAUDE.md by name among its four source files and verifies every falsifiable claim against the cited code by static comparison first. claude-md-improver then grades coverage, architecture clarity, and conciseness and proposes targeted diffs -- against a file whose claims are now known-accurate, not merely plausible."
    prompt: "check whether CLAUDE.md's claims still match the code before you touch anything in it -- then grade its quality and propose targeted additions"
    dos:
      - "Run the drift check first, every time -- it's the only citation-by-citation verification either skill does."
      - "Treat every claim the drift check confirms as stale as something to fix, not just extend around."
    donts:
      - "Don't let claude-md-improver's Phase 2 currency score stand in for a real per-claim check -- it's a graded eyeball pass, not static verification."
      - "Don't skip straight to drafting additions on a CLAUDE.md nobody has fact-checked recently."
    grounding: "this repo's own CLAUDE.md, dense with falsifiable claims -- \"rrt-doctor's own hook manifest pins it to stages: [manual]\", the six-defect table, the open self-assess:arch-health-auditor tool-grant anomaly -- exactly what self-assess-docs-drift is built to check."
    recipeTask: "Improve a stale CLAUDE.md without trusting its own claims"
    recipeUrl: "/catalog/surface/improve-a-stale-claude-md"

  - id: "self-assess-lint-audit-hookify"
    skillA: "self-assess:self-assess-lint-audit"
    skillB: "hookify:hookify"
    source: "claude-plugins-official"
    beat: "verify"
    why: "self-assess-lint-audit is explicitly read-only and never auto-fixes a violation it confirms, which leaves nothing standing guard against the next repeat -- and a plugin-wide, code-reviewed hook is the wrong weight class for one contributor's own habit."
    how: "self-assess-lint-audit extracts discrete rules from CLAUDE.md (this repo has no house-rules.md, so every rule is labeled \"CLAUDE.md (best-effort)\") and dispatches convention-auditor to confirm real violations against the actual code. hookify then turns one confirmed, repeatedly-broken rule into a live `.claude/hookify.<name>.local.md` guard, active on the next tool use with no restart."
    prompt: "I keep forgetting the rrt-over-raw-git rule -- warn me immediately, right now, the next time I run a bare git commit or push in this repo"
    dos:
      - "Confirm the violation with self-assess-lint-audit's Find+Verify before authoring a guard -- hookify's own rule format has no way to check whether a pattern match is a real violation, only to react once one's typed."
      - "Scope the guard personally and locally (.claude/*.local.md, gitignored) -- it's for one contributor's habit, not a policy the whole plugin ships with."
    donts:
      - "Don't treat a hookify rule as equivalent-strength to a shipped PreToolUse hook -- hookify's own pretooluse.py fails OPEN on any exception (\"allow operation and log error\"), the opposite of this repo's fail-closed doctrine."
      - "Don't reach for hookify to enforce a rule across the whole plugin -- that's `make-strategy-enforced-not-documented`'s job (cupertino-handbook-draft/check + plugin-dev:hook-development), which produces a shipped, fail-closed hook, not a personal local one."
    grounding: "CLAUDE.md's own rule \"Prefer rrt over raw git for repo-level operations\" is exactly the shape of rule a contributor could keep forgetting; hookify's hooks.json wires real `type: \"command\"` hooks for PreToolUse/PostToolUse/Stop/UserPromptSubmit."
    recipeTask: "Convert a documented rule you keep breaking into an immediate personal guard"
    recipeUrl: "/catalog/quality-verification/convert-a-broken-rule-into-a-personal-guard"

  - id: "self-assess-portfolio-project-artifact"
    skillA: "self-assess:self-assess-portfolio"
    skillB: "project-artifact:project-artifact"
    source: "claude-plugins-official"
    beat: "verify"
    why: "self-assess-portfolio's own output is deliberately narrow -- one grade per repo, worst-signal-wins, written once to a local file with no sharing and no memory of the previous sweep."
    how: "self-assess-portfolio grades every repo in an explicit portfolio directory Red/Amber/Green/Gray and writes self-assess-portfolio.html into that directory. project-artifact then turns those verdicts into a living claude.ai page -- status pills, an Attention tab for what's blocked, and a delta-only refresh that reads the previous render's embedded state block."
    prompt: "sweep every repo under ~/LocalDocuments/GitHub_Forks and grade each one's self-assess health, then publish that as a shareable status page I can send the team"
    dos:
      - "Name the portfolio directory explicitly when invoking self-assess-portfolio -- its own gate refuses to infer cwd's parent as the portfolio."
      - "Let project-artifact read the previous render's state block on every refresh so re-running the sweep reports a delta, not a repeated wall of rows."
    donts:
      - "Don't republish the raw self-assess-portfolio.html as-is -- it has no sharing, no tabs, and no delta tracking across sweeps."
      - "Don't let a Gray verdict get smoothed into an invented grade on the status page -- Gray means \"not yet assessed,\" nothing more."
    grounding: "the user's own ~/LocalDocuments/GitHub_Forks directory holds roughly 150 git repositories, including werkstoff itself -- exactly the \"explicit portfolio directory\" self-assess-portfolio's Step 1 scope gate requires."
    recipeTask: "Publish a multi-repo portfolio sweep as a living, shareable status page"
    recipeUrl: "/catalog/surface/publish-a-portfolio-sweep-as-a-status-page"

  - id: "self-assess-docs-drift-comment-analyzer"
    skillA: "self-assess:self-assess-docs-drift"
    skillB: "pr-review-toolkit:comment-analyzer"
    source: "claude-plugins-official"
    beat: "verify"
    why: "Docs drift is asymmetric -- the code moves and the prose doesn't -- and comments drift from the same edit as docs, but no docs sweep reads them."
    how: "self-assess-docs-drift verifies every extracted, in-scope claim against the current codebase, run immediately after a change while the diff is still legible. pr-review-toolkit:comment-analyzer separately checks the comments in the same touched files, since a docs sweep doesn't read those."
    prompt: "we renamed several things this week -- check whether the docs still describe what the code actually does"
    dos:
      - "Run the sweep immediately after the change, while the diff that caused the drift is still legible."
      - "Check comments and docs as two separate passes -- the same edit drifts both, but nothing reads them together."
    donts:
      - "Don't wait -- run months later, this sweep produces a backlog instead of a fix."
      - "Don't run a convention survey (codebase-consistency:pattern-analyst) until the docs are already accurate -- a survey run before the content is correct clusters variants of the wrong text."
    grounding: ".rrt.toml declares [[tool.rrt.docs.shared_blocks]], which regenerates the rrt:auto:start:example-prompts-intro block in every plugin README -- a drift sweep must distinguish generated prose from hand-written prose before reporting either."
    recipeTask: "Sweep documentation drift after a change"
    recipeUrl: "/catalog/surface/documentation-drift-after-a-change"
---

# Pairings: which two skills combine, and why

The [prompt catalog](/catalog/) is indexed by what you're trying to do -- pick a task,
get an ordered sequence of beats. This page is the other axis: pick two skills, find out
whether combining them is grounded in anything real, and if so, what the combination
actually buys.

Every card below pairs one werkstoff skill with one skill or agent from `superpowers` or
one of the official Anthropic plugins (`pr-review-toolkit`, `code-modernization`,
`feature-dev`, `frontend-design`, `plugin-dev`). Read
[orchestration/README.md](../) first if you haven't -- it explains the three roles
(werkstoff as specialised inspector, superpowers as process discipline, the official set
as named reviewer agents) and the four beats these cards are grouped by.

<PairingCards />

## How to read a pairing card

Each card names two skills, the beat they occupy (Inspect and research, Split into
workstreams, Execute in parallel, or Verify -- see
[orchestration/README.md](../#the-four-beats)), and five things:

- **Why** -- the failure mode that combining them, rather than running either alone,
  actually closes.
- **How** -- the sequencing: which one runs first, and what it hands the other.
- **Example prompt** -- a real, copy-pasteable prompt, quoted unedited from the catalog
  recipe the pairing is drawn from.
- **Do / Don't** -- concrete constraints pulled from the skills' own stated scope, from
  [`gates.md`](gates.md), [`routing.md`](routing.md), or from this repo's own `CLAUDE.md`
  -- never generic advice.
- A **grounding** line naming the real file, defect, or repo state the pairing was
  checked against, and a link back to the full catalog recipe it's excerpted from.

## Where this data comes from, and what didn't make it

Nothing here is invented. Every pairing is two adjacent (or closely linked) beats from
an existing [catalog](/catalog/) recipe, or one of the three pairings orchestration/README.md's
"Worked examples" section already quotes in full. A plausible-sounding combination with
no recipe behind it -- no real `why`, no real prompt, no real grounding -- is not on this
page. Extending this list means writing a new catalog recipe with real beats and a real
prompt first; a card here without one behind it would be exactly the kind of
plausible-but-false content `confab` exists to catch.

Three recipes in the catalog are marked "No werkstoff fit" -- pure Superpowers tasks with
no werkstoff skill to pair against. They don't appear here for the same reason: there is
no pairing to show, and a forced one would be worse than none.
