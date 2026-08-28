# Extended prompt catalog

The eight werkstoff plugin READMEs — the seven capability plugins plus `takt`, the
sequencing hook — already carry 74 example prompts between them, but
every one of those prompts is indexed **by plugin** — a reader who already knows that
`compass` exists can find the compass prompt. A reader who arrives holding a task rather
than a plugin has no entry point at all. This catalog is the second door: the same
capability surface, indexed by development task.

## How to read an entry

Each entry names a task, then lays out its **beats** — the ordered moments where a skill
or agent earns its place — then gives prompts that fire those beats, then closes with a
worked example drawn from this repository.

| Column | Meaning |
|---|---|
| Beat | The moment in the task, not the tool |
| Fires | `plugin:skill`, or `plugin:agent` marked `(agent)` |
| Why here, not later | What is lost if the beat slides to a different position |

Three conventions hold throughout.

**Leaves only.** Beats name leaf skills and dispatchable agents. Orchestrators —
`andon:andon-loop`, `self-assess:self-assess-autopilot`, `compass:compass-solve`,
`cupertino:cupertino-review`, `confab:confab-cycle`, the `/consistency-*` command chain,
`code-modernization`'s eight-stage pipeline — each own a whole task and must never be
wedged in as a step inside another workflow. Choosing between them is a routing question;
see `routing.md`.

**Declared position is binding.** A skill whose own frontmatter says "before any code"
does not get retrofitted afterwards. `cupertino:cupertino-council` states it directly:
"Always run before code, never after — retrofitting the council onto finished code
defeats the purpose." `compass:compass-clarify-scope` declares itself for use "before any
work begins". `codebase-consistency` is the mirror case: genuinely post-hoc, and wrong as
a preamble.

**Honest gaps.** Three entries below are marked **No werkstoff fit**. Those tasks are
better served by Superpowers alone, and saying so is more useful than a forced pairing.

Where an entry dispatches several agents at once, one rule from
`superpowers:subagent-driven-development` applies verbatim: "Always specify the model
explicitly when dispatching a subagent. An omitted model inherits your session's model —
often the most capable and most expensive — which silently defeats this section."
Mechanical fan-out goes to the cheap tier; integration and judgment to the standard tier;
architecture and any final whole-branch review to the most capable tier.

## Before any code

### Verify the brief's premises before acting

Most bad work is correct work aimed at a premise that was never true. A brief arrives
asserting where something lives, what a job does, or which package is already a
dependency — and the cheapest possible moment to test those assertions is before a single
file is opened for editing.

| Beat | Fires | Why here, not later |
|---|---|---|
| Extract the brief's load-bearing claims | `compass:compass-verify-assumptions` | Once implementation starts, a false premise is discovered as a bug rather than as a claim |
| Attach a file:line to each surviving claim | `compass:compass-ground-evidence` | Grounding is cheap on five claims and expensive on a finished diff |
| If the brief names packages, confirm they exist | `confab:confab-dependency-audit` | A hallucinated or typosquat-adjacent package name is free to catch now and a supply-chain incident later |

##### Test the brief before trusting it

````prompt
"before we do any of this, list the assumptions this request is resting on and tell me which ones you can't actually confirm"
````

> Triggers `compass-verify-assumptions` — separates what the brief asserts from what the
> repository shows, and marks each assertion confirmed, refuted, or unresolved.

##### Refuse ungrounded claims

````prompt
"don't make this up — every claim about this repo needs a file and line number behind it"
````

> Triggers `compass-ground-evidence` — requires a file:line, URL, or explicitly-flagged
> prior knowledge behind every factual claim, and refuses to assert anything unverified.

##### Check the package names are real

````prompt
"the plan names three new dependencies — check they actually exist on the registry before we add any of them"
````

> Triggers `confab-dependency-audit` — bounded read-only registry lookups with an
> independent verification pass, flagging nonexistent and typosquat-adjacent entries.

**Worked example —** a brief asserting that the symbol indexer lives only in
`tools/symbol-indexer/` collapses on the first grounding pass: five plugins each carry a
byte-identical `scripts/build_symbol_index.py`.

### Read-only design study with an evidence legend

A design study is worth reading only if its confidence is legible. The trap is a study
that mixes what was checked with what was assumed and marks neither. A two-symbol legend
fixes it: **[V]** for a claim carrying a file:line or URL, **[P]** for a claim that is
provisional — inferred, plausible, and explicitly flagged as unverified.

| Beat | Fires | Why here, not later |
|---|---|---|
| Follow the evidence where it leads | `compass:compass-investigate-dynamically` | The next thing worth reading is decided by the last observation; a pre-planned file list misses it |
| Build the relationship index the study rests on | `compass:compass-map-relationships` | Multi-hop claims need a traversable triple index, not recollection |
| Enforce the legend at claim level | `compass:compass-ground-evidence` | The [V]/[P] split is exactly this skill's file:line-or-flagged-prior-knowledge rule |
| Emit the study as a citation-bearing trace | `compass:compass-summarize-trace` | A study whose reasoning is not reconstructible cannot be audited by its reader |

##### Study without touching anything

````prompt
"read-only please: I want to understand how this works before anyone changes it. Don't edit a single file."
````

> Triggers `compass-investigate-dynamically` — runs a Reasoning/Action/Observation loop
> where each observation decides the next step, for cases where the sequence of actions
> cannot be planned upfront.

##### Mark verified against provisional

````prompt
"write this up with a legend: [V] for anything you can cite a file:line for, [P] for anything you're inferring. Nothing unmarked."
````

> Triggers `compass-ground-evidence` — every factual claim carries a file:line, a URL, or
> an explicit provisional flag; unverifiable claims are refused rather than smoothed over.

##### Trace the chain, hop by hop

````prompt
"trace how a change in the shared script would reach each plugin's output"
````

> Triggers `compass-map-relationships` — extracts indexed relationship triples and
> traverses them hop by hop, citing the triple index at every hop.

**Worked example —** a read-only study of how the four werkstoff `PreToolUse` hooks
interact, covering `plugins/andon/hooks/`, `plugins/self-assess/hooks/`,
`plugins/confab/hooks/`, and `plugins/cupertino/hooks/`, with each interaction marked [V]
or [P].

### Scope an ambiguous task

"Make the plugins consistent" is not a task; it is four tasks wearing one coat. Scoping
work belongs strictly before anything else, because every later decision inherits the
ambiguity unchanged.

| Beat | Fires | Why here, not later |
|---|---|---|
| Surface the fuzzy phrasing and unstated success criteria | `compass:compass-clarify-scope` | Declared for use "before any work begins"; run afterwards it merely renames a finished decision |
| Explore the genuinely different readings | `compass:compass-explore-branches` | Scoring alternatives after one has been built anchors on the built one |
| Fold the best of two readings together | `compass:compass-negotiate-tradeoffs` | Hybrids are only checkable while both source branches are still scored and live |
| Commit the settled scope to a plan | `superpowers:writing-plans` | A scope that never becomes a written plan is re-litigated at every subsequent step |

##### Pin down what is actually being asked

````prompt
"the scope of this request is fuzzy — pin it down before anyone starts"
````

> Triggers `compass-clarify-scope` — surfaces ambiguous phrasing and unstated success
> criteria before any work starts.

##### Generate readings that do not anchor on each other

````prompt
"before we commit to an approach, give me a few genuinely different readings of this request and score them"
````

> Triggers `compass-explore-branches` — proposes and scores multiple viable approaches
> instead of anchoring on the first, each branch generated independently.

##### Write the settled scope down

````prompt
"we've agreed the scope — turn it into a written plan with steps before touching code"
````

> Triggers `superpowers:writing-plans` — converts a settled spec into a step-by-step
> implementation plan that a separate session can execute.

**Worked example —** "make the plugins consistent" splits on a documented boundary:
`plugins/codebase-consistency/README.md` lines 28-47 are headed "Scope - read this before
installing both this and self-assess", and route documented conventions and
version-deprecated idioms out of `codebase-consistency` and into `self-assess`. Which of
the two owns the request is a scoping answer, not an implementation detail.

### Scaffold a new project or CLI

Scaffolding is the one task where the doctrine must be loaded before the generator runs,
because a scaffold that violates the doctrine is cheaper to regenerate than to retrofit.

| Beat | Fires | Why here, not later |
|---|---|---|
| Settle what is being built and why | `superpowers:brainstorming` | Required before any creative work; a scaffold generated from an unexamined idea encodes the idea's flaws structurally |
| Load the production-grade doctrine | `cli-scaffold:cli-architecture` | Its own instruction: load "BEFORE any paradigm skill ... generates a scaffold" |
| Generate against the doctrine | `cli-scaffold:cli-scaffold-interpreted` | Paradigm choice (compiled / interpreted / shell) is fixed by language and cannot be swapped later without regenerating |
| Verify the scaffold read-only | `cli-scaffold:cli-scaffold-verifier` (agent) | Checks the five pillars and the frozen 0/1/2 exit-code contract while the scaffold is still disposable |

##### Design the thing before generating it

````prompt
"I want to build a small CLI for this. Let's brainstorm what it should do before any code exists."
````

> Triggers `superpowers:brainstorming` — explores intent, requirements, and design before
> implementation, and is required before any creative work begins.

##### Generate a production-grade scaffold

````prompt
"scaffold a production-grade Python CLI for this, following the architecture doctrine rather than a bare template"
````

> Routes through `scaffold-cli` to the interpreted-paradigm skill, which loads
> `cli-architecture` first and generates against the five-pillar doctrine.

##### Check the scaffold against the doctrine

````prompt
"verify the scaffold you just generated against the five pillars — read-only, don't fix anything yet"
````

> Triggers `cli-scaffold-verifier` — read-only verification that reports gaps as either
> fixable or needs-human-judgment, and never edits, builds, installs, or publishes.

**Worked example —** `tools/werkstoff-cli/` is the shape a sibling CLI in this repo should
match: a `src/werkstoff/` package split into `cli.py` and `core.py`, snapshot tests under
`tests/__snapshots__/`, and a `pyproject.toml` pinning `requires-python = ">=3.12"`.

## CI & release

### Pipeline red across several jobs

Several jobs red at once is usually one cause with several symptoms, or several unrelated
causes that must not be debugged as one. The first move is telling those two cases apart.

| Beat | Fires | Why here, not later |
|---|---|---|
| Audit the CI configuration itself | `self-assess:self-assess-ci-topology` | A config-level defect explains all the symptoms at once; chasing symptoms first wastes the whole first pass |
| Split independent failures into stages | `compass:compass-decompose-chain` | Derives which failures are genuinely independent and can be worked in parallel, from the dependency graph rather than by guess |
| Debug each genuinely separate failure | `superpowers:systematic-debugging` | Required before proposing any fix; a fix proposed ahead of a root cause is a second failure mode |

##### Audit the pipeline before the failures

````prompt
"several CI jobs went red at once — audit the CI config itself before we look at any individual failure"
````

> Triggers `self-assess-ci-topology` — audits git remote topology and CI configuration
> for redundancy, mirror risk, and drift against the CI documentation.

##### Separate the failures that are actually one failure

````prompt
"break these five red jobs into independent tracks — tell me what depends on what and what can be worked in parallel"
````

> Triggers `compass-decompose-chain` — splits the problem into a 2-5 stage pipeline with
> explicit input/output contracts per stage, and derives the parallelizable set.

##### Find the root cause of each track

````prompt
"work the lint failure to root cause first — no fixes proposed until the cause is nailed down"
````

> Triggers `superpowers:systematic-debugging` — the mandatory pre-fix discipline for any
> bug, test failure, or unexpected behavior.

**Worked example —** `.github/workflows/plugin-checks.yml` runs seven checks with
`continue-on-error: true` and collapses them into a single "Fail the job if any check
failed" step. One red job can therefore mean any of seven independent causes, which is
exactly the shape this entry exists to untangle.

### Cross-forge CI parity

Two execution surfaces claiming to run "the same checks" drift silently, because nothing
compares them. The trap is that both surfaces are green and neither is running what the
documentation says it runs.

| Beat | Fires | Why here, not later |
|---|---|---|
| Audit remotes, mirrors, and CI config against the docs | `self-assess:self-assess-ci-topology` | Drift against CI documentation is precisely this skill's declared scope |
| Index which check is defined where | `compass:compass-map-relationships` | Parity is a multi-hop claim across files; it needs a traversable index, not a reading |
| Check the docs still describe the pipelines | `self-assess:self-assess-docs-drift` | Documentation drift is what let the surfaces diverge unnoticed in the first place |

##### Audit the topology, not the runs

````prompt
"audit our remotes and CI configuration for redundancy and drift — I want to know whether the surfaces actually run the same checks"
````

> Triggers `self-assess-ci-topology` — checks remote topology and CI config for
> redundancy, mirror risk, and drift against what the CI documentation claims.

##### Map check-to-surface

````prompt
"map every check we run to the surface that defines it, and show me which surface is missing which check"
````

> Triggers `compass-map-relationships` — extracts indexed relationship triples across the
> config files and traverses them, citing the index at each hop.

##### Verify the docs still describe reality

````prompt
"check whether our CI documentation still matches what the workflows actually do"
````

> Triggers `self-assess-docs-drift` — verifies every extracted, in-scope documentation
> claim against the current state of the codebase.

**Worked example —** this repo has two check surfaces and they are not aligned.
`.pre-commit-config.yaml` runs three `rrt` hooks; `.github/workflows/plugin-checks.yml`
runs pre-commit plus five further steps. Action pins drift across workflows too —
`actions/checkout@v4` and `actions/setup-python@v5` in `plugin-checks.yml` against
`actions/checkout@v7` and `actions/setup-python@v6` in `cicd.yml` and
`auto-version-bump.yml`.

### A job reports success but changed nothing

The most expensive CI defect is the green one. A job exits zero, the badge stays green,
and the work it was supposed to do never happened. Conditional skips, swallowed errors,
and unmatched patterns all produce this shape.

| Beat | Fires | Why here, not later |
|---|---|---|
| Hunt swallowed errors and inappropriate fallbacks | `pr-review-toolkit:silent-failure-hunter` (agent) | Purpose-built for exactly this shape: silent failures, inadequate error handling, and fallback behavior that suppresses the real outcome |
| State and prove the contract the job is supposed to satisfy | `andon:andon-verify` | A green exit code is not evidence; the wire "job ran → artifact changed" has to be proven independently |
| Confirm the effect is asserted somewhere | `confab:confab-assertion-audit` | If nothing asserts the job's effect, the next silent skip is invisible again |

##### Hunt the silent success

````prompt
"this job exits zero but nothing downstream changed — go hunt for swallowed errors, skipped branches, and fallbacks that hide the real outcome"
````

> Triggers `silent-failure-hunter` — zero-tolerance review for suppressed errors,
> inadequate handling, and fallbacks that convert a failure into a quiet success.

##### Prove the job's actual effect

````prompt
"prove the wire: this job is supposed to produce a version bump. Show me evidence it did, not that it exited zero."
````

> Triggers `andon-verify` — routes the wire to one of seven evidence-grounded strategies
> and returns a structured green/red verdict; it never writes the ledger.

##### Check the effect is asserted at all

````prompt
"is there any test or check that would fail if this job silently did nothing?"
````

> Triggers `confab-assertion-audit` — proposes plausible small mutations and judges
> whether existing tests would actually catch each one.

**Worked example —** `.github/workflows/auto-version-bump.yml` skips entirely when the
head commit message does not start with a recognized conventional-commit type; its own
header comment records that a plain-English PR title "is silently skipped, by design".
The run is green and bumps nothing — the exact shape `silent-failure-hunter` is built for.

### A release path that has never succeeded

**No werkstoff fit — this is pure Superpowers.** `andon-verify` proves a wire from
evidence that the wire has already produced. A release path that has never run has
produced no evidence to route, so there is nothing for it to prove; and no werkstoff skill
rehearses an unexercised path. The honest workflow is Superpowers-only.

| Beat | Fires | Why here, not later |
|---|---|---|
| Enumerate everything that must be true for the path to work | `superpowers:brainstorming` | The failure modes of an unexercised path are unknown, not undiscovered; they have to be generated |
| Write the rehearsal down as a plan | `superpowers:writing-plans` | An untested release path is a multi-step task, and the steps must survive a failed first attempt |
| Rehearse in an isolated workspace | `superpowers:using-git-worktrees` | A rehearsal that mutates the real branch converts a dry run into an incident |
| Refuse to declare it working on a green badge | `superpowers:verification-before-completion` | "It ran" and "it produced the artifact" are different claims, and only the second matters |

##### Enumerate the preconditions

````prompt
"this release workflow has never actually run. Before we trigger it, list everything that has to be true for it to succeed."
````

> Triggers `superpowers:brainstorming` — explores requirements and failure modes before
> any execution, which is the only available substitute for prior evidence.

##### Rehearse somewhere disposable

````prompt
"set up an isolated worktree so we can rehearse this release without touching the real branch"
````

> Triggers `superpowers:using-git-worktrees` — ensures an isolated workspace exists via
> native tooling or a git worktree fallback before risky work begins.

##### Do not accept green as done

````prompt
"don't tell me it worked because the workflow went green — show me the artifact it was supposed to produce"
````

> Triggers `superpowers:verification-before-completion` — blocks a completion claim that
> rests on a proxy signal rather than the actual required output.

**Worked example —** `.github/workflows/batch-release.yml` is `workflow_dispatch`-only and
reaches the bump-and-tag loop through `workflow_call` into `auto-version-bump.yml`. That
reuse path has a different trigger surface from the push path exercised on every merge, so
its first real run is also its first test.

### Supply-chain pinning and dependency audit

Two different questions hide under one heading. "Does this package exist?" is answerable
against a registry. "Is this reference pinned tightly enough to be reproducible?" is a
policy question about mutable refs, and no werkstoff skill answers it.

| Beat | Fires | Why here, not later |
|---|---|---|
| Confirm every declared dependency is real | `confab:confab-dependency-audit` | Hallucinated and typosquat-adjacent entries are cheapest to catch at declaration time, before a lockfile blesses them |
| Scan for CVEs, secrets, and injection surface | `code-modernization:security-auditor` (agent) | A standalone adversarial leaf; dispatched directly, without adopting the modernization pipeline |
| Verify the pinning claim as a wire | `andon:andon-verify` | "Everything is pinned" is a contract; a float tag silently violates it and only evidence catches that |

##### Audit the manifests against the registry

````prompt
"audit every dependency in our manifests — I want to know if any of them don't actually exist or look like typosquats"
````

> Triggers `confab-dependency-audit` — bounded read-only registry lookups with a
> mandatory independent verification pass; a registry timeout is never treated as a
> verdict.

##### Scan the security surface

````prompt
"run an adversarial security pass over this repo — OWASP, CVEs in dependencies, secrets, injection"
````

> Dispatches `security-auditor` directly as a standalone leaf, without invoking the
> `code-modernization` pipeline around it.

##### Prove the pinning claim

````prompt
"we claim every third-party reference is pinned. Prove it or refute it with evidence."
````

> Triggers `andon-verify` — treats the pinning claim as a wire with a stated contract and
> returns a structured green/red verdict rather than an impression.

**Worked example —** every `uses:` reference in `.github/workflows/` is a float tag, not a
commit SHA: `actions/checkout@v7`, `anchore/sbom-action@v0`,
`actions/attest-build-provenance@v4`, and `pypa/gh-action-pypi-publish@release/v1` — the
last a moving branch ref inside the publish path that already emits an SBOM and a
provenance attestation.

## Defect work

### Root-cause bugfix from a tracked issue

The spine of this task is Superpowers: root cause before fix, failing test before code.
The werkstoff contribution is the search and the proof at either end.

| Beat | Fires | Why here, not later |
|---|---|---|
| Find where the behavior actually lives | `compass:compass-investigate-dynamically` | The location is unknown; a pre-planned file list cannot adapt to what each observation reveals |
| Reach a root cause before any fix is proposed | `superpowers:systematic-debugging` | Mandatory before proposing fixes; a fix without a cause is a guess with a diff |
| Write the failing regression test first | `superpowers:test-driven-development` | A regression test written after the fix passes for the wrong reason |
| Prove the fix against a stated contract | `andon:andon-verify` | Self-review is generous; the tribunal strategy dispatches defender and challenger blind to each other |

##### Locate the behavior

````prompt
"I don't know where this behavior is implemented — go find it before we talk about fixing it"
````

> Triggers `compass-investigate-dynamically` — a Reasoning/Action/Observation loop where
> each observation decides the next step.

##### Cause first, fix second

````prompt
"work this to root cause. No fix, no patch, no workaround until the cause is proven."
````

> Triggers `superpowers:systematic-debugging` — the required pre-fix discipline for any
> bug, test failure, or unexpected behavior.

##### Failing test before implementation

````prompt
"write the failing regression test for this bug first, then fix it"
````

> Triggers `superpowers:test-driven-development` — the test must fail for the right
> reason before implementation code exists.

##### Prove it, adversarially

````prompt
"run the tribunal on this fix — I want a defender, a challenger, and someone who actually runs the checks"
````

> Triggers `andon-verify` strategy a — `andon-defender` and `andon-challenger` dispatched
> in parallel and blind to each other, `andon-verifier` reproducing facts, and
> `andon-adjudicator` deciding per criterion.

**Worked example —** the failure mode recorded in `.github/workflows/plugin-checks.yml`:
a `.gitignore` regression that silently drops a vendored file, leaving the artifact lock
expecting a file that no longer exists — a bug whose symptom appears months later, at a
hook denial, rather than where the cause lives.

### A fix that did not stick

A bug reported fixed and then seen again means one of three things: the fix addressed a
symptom, the fix regressed, or the fix was never proven in the first place. All three are
verification failures, not coding failures.

| Beat | Fires | Why here, not later |
|---|---|---|
| Test the claim that it was ever fixed | `compass:compass-verify-assumptions` | "It was fixed in the last pass" is an assumption; re-implementing on top of it repeats the original mistake |
| Re-prove the wire, blind to the prior verdict | `andon:andon-verify` | Its tribunal agents are dispatched "never authored or influenced by the session that proposed or built the fix under review" |
| Check whether any test would have caught the regression | `confab:confab-assertion-audit` | A fix that no test guards is a fix scheduled to un-stick again |

##### Question the previous fix

````prompt
"this was supposedly fixed last week and it's back. What are we assuming about that fix that might not be true?"
````

> Triggers `compass-verify-assumptions` — separates the fix claim from the fix evidence
> and marks each confirmed, refuted, or unresolved.

##### Re-prove it, blind

````prompt
"re-verify this fix from scratch — don't read the previous verdict, and don't let whoever wrote the fix judge it"
````

> Triggers `andon-verify` — the tribunal is dispatched fresh and blind to any prior
> verdict, and never authored by the session that built the fix.

##### Ask what would catch the next regression

````prompt
"if this bug came back tomorrow, would anything in the test suite go red?"
````

> Triggers `confab-assertion-audit` — proposes plausible mutations at the fix site and
> judges whether existing tests would catch each one.

**Worked example —** re-proving the "Verify vendored artifacts match their committed lock"
check by removing one `plugins/*/assets/inline-d3.html` in a disposable worktree and
confirming `rrt artifacts --check --strict` actually goes red, rather than trusting that
it would.

### Misleading error or diagnostic output

An error message that names the wrong cause costs more than no message at all, because it
buys a confident wrong hypothesis. This is the one commodity surface `cupertino` claims
explicitly, and the pairing is easy to miss.

| Beat | Fires | Why here, not later |
|---|---|---|
| Elevate the commodity surface while it is in scope | `cupertino:cupertino-elevate` | Its frontmatter scopes it to "a low-status commodity feature already in scope for the current build - error messages, logs, config, settings, onboarding" |
| Check the diagnostic is not covering a swallowed failure | `pr-review-toolkit:silent-failure-hunter` (agent) | A misleading message is often the visible half of a suppressed error; fixing the wording alone leaves the suppression |
| Check the comments around it are not also lying | `pr-review-toolkit:comment-analyzer` (agent) | Comment rot and message rot come from the same edit that moved the behavior |

##### Elevate the error surface

````prompt
"our error messages are technically accurate and completely useless. Treat them as a first-class surface, not an afterthought."
````

> Triggers `cupertino-elevate` — applies design attention to a low-status commodity
> surface that is already in scope for the current build.

##### Check what the message is hiding

````prompt
"this error text points at the wrong cause — check whether something upstream is swallowing the real failure"
````

> Triggers `silent-failure-hunter` — looks for suppressed errors and fallbacks that
> reshape a real failure into a misleading one.

##### Audit the surrounding comments

````prompt
"check whether the comments around this error path still describe what the code does"
````

> Triggers `comment-analyzer` — verifies comments against actual code behavior and flags
> comment rot as maintenance debt.

**Worked example —** the resolve step in `.github/workflows/plugin-release.yml` exits with
`Unknown plugin group '$GROUP' from tag '$TAG'` — accurate, but silent on the fact that
the allowed set is a hardcoded seven-name `case` list in the same file, which is what a
reader actually needs to know.

### Tests pass while the code is broken

A green suite proves the tests ran, not that they would notice. The specific trap worth
naming: an assertion whose expected value brackets a hardcoded default, so the test passes
whether or not the logic under it ever executes.

| Beat | Fires | Why here, not later |
|---|---|---|
| Mutate the source and see what survives | `confab:confab-assertion-audit` | Proposes off-by-one, boundary-flip, and condition-negation mutations and judges whether any existing test catches them |
| Judge behavioral coverage, not line coverage | `pr-review-toolkit:pr-test-analyzer` (agent) | Coverage percentages are compatible with assertions that assert nothing |
| Prove the suite is itself a valid oracle | `andon:andon-verify` | One of its seven strategies is verify-the-verifier — the right shape when the checker is what is suspect |

##### Mutate and see what survives

````prompt
"mutate this module — flip a boundary, negate a condition, shift an index — and tell me which mutations the tests would not catch"
````

> Triggers `confab-assertion-audit` — runs a real mutation tool read-only when one is
> named and available, and otherwise reasons the mutations through with that fallback
> explicitly noted.

##### Judge the coverage that matters

````prompt
"review the tests on this branch for behavioral coverage, not line coverage — where are the real gaps?"
````

> Triggers `pr-test-analyzer` — assesses test quality and completeness and rates gaps by
> criticality rather than by metric.

##### Verify the verifier

````prompt
"I don't trust this test suite. Verify the verifier before we trust anything it says."
````

> Triggers `andon-verify` — routes to its verify-the-verifier strategy when the checker
> itself is the artifact under suspicion.

**Worked example —** auditing `plugins/confab/scripts/test_cycle_engine.py` and
`tools/enforcement-audit/test_audit_enforcement.py` for assertions whose expected value is
the same hardcoded default the code falls back to when the real path never runs.

### Incident triage under time pressure

**No werkstoff fit — this is pure Superpowers.** Every werkstoff skill in the defect space
is evidence-accumulating and gate-heavy by design: `andon-verify` dispatches a
four-agent tribunal, `confab-assertion-audit` runs a mutation pass, and
`compass-ground-evidence` refuses unverified claims. Those properties are exactly right
for a fix that must hold and
exactly wrong for a page at 02:00. Force-fitting them here would be the catalog's worst
advice.

| Beat | Fires | Why here, not later |
|---|---|---|
| Cause before mitigation, compressed but not skipped | `superpowers:systematic-debugging` | The pressure to skip this step is what turns one incident into three |
| Fan out across independent hypotheses at once | `superpowers:dispatching-parallel-agents` | Its own rule: "Multiple dispatch calls in one response = parallel execution. One per response = sequential." Under time pressure that difference is the whole game |
| Refuse to close on a proxy signal | `superpowers:verification-before-completion` | "The alert cleared" and "the cause is gone" are different claims |

##### Compress, do not skip, the root cause

````prompt
"production is down. Work the root cause fast, but work it — no speculative reverts."
````

> Triggers `superpowers:systematic-debugging` — the pre-fix discipline, applied at
> incident tempo rather than abandoned.

##### Fan out on hypotheses simultaneously

````prompt
"send three investigators at once — one on the deploy, one on the config change, one on the upstream dependency. Same message, don't serialize them."
````

> Triggers `superpowers:dispatching-parallel-agents` — multiple dispatch calls in a
> single response run genuinely in parallel; one per response silently serializes them.

##### Do not close on the alert clearing

````prompt
"before we close this out, show me the cause is actually gone — not just that the alert stopped"
````

> Triggers `superpowers:verification-before-completion` — blocks completion claims that
> rest on a proxy signal.

**Worked example —** a red `plugin-checks.yml` blocking every open pull request in this
repo at once: the triage move is parallel investigators across the seven
`continue-on-error` steps, not a tribunal on any one of them.

## Change to existing code

### Refactor for maintainability

Refactoring's defining constraint is that behavior must not change — which makes the
before-picture and the after-proof more important than the edit itself.

| Beat | Fires | Why here, not later |
|---|---|---|
| Measure where the debt actually is | `self-assess:self-assess-complexity-score` | Refactoring by intuition targets the code that is annoying rather than the code that is costly |
| Map the real dependency graph | `self-assess:self-assess-arch-health` | God-modules, cycles, and layering violations are structural findings; a refactor that ignores them relocates the problem |
| Pin behavior before changing it | `superpowers:test-driven-development` | Characterization tests written after the refactor characterize the refactor |
| Check contracts survived | `confab:confab-contract-drift` | Its own description scopes it to checking "for contract drift after a refactor" |
| Only then, re-derive behavioral equivalence | `codebase-consistency:equivalence-verifier` (agent) | Genuinely post-hoc: it re-checks that the module behaves identically to before and that its docs and comments still match, from the diff rather than from the refactorer's own report |

##### Find the expensive code, not the annoying code

````prompt
"measure complexity and size per module so we refactor where the debt actually is"
````

> Triggers `self-assess-complexity-score` — dispatches one surveyor per stage for SLOC,
> file count, and cyclomatic complexity, producing a prioritization index.

##### Check the structure before touching it

````prompt
"check this repo's architecture health — god modules, cycles, layering violations, with evidence"
````

> Triggers `self-assess-arch-health` — judges the real stage/wire dependency graph and
> confirms every mechanically-flagged candidate against actual source.

##### Verify no contract moved

````prompt
"check for contract drift after this refactor — signatures, type hints, docstring params, schemas"
````

> Triggers `confab-contract-drift` — compares machine-checkable declarations against
> actual call-site and handler usage, reporting both locations for each mismatch.

**Worked example —** `tools/plugin-serializer/` holds four scripts —
`build_inventory.py`, `contract_diff.py`, `extract_behavior.py`, `generate_plugin.py` —
whose shared assumptions about plugin shape make it a real candidate for the
measure-then-map-then-pin sequence above.

### Collapse duplication hand-synced across N sites

N byte-identical copies kept in step by hand is a defect with a countdown. The trap is
that collapsing them looks trivial and the risk lives entirely in the sites that were
about to diverge.

| Beat | Fires | Why here, not later |
|---|---|---|
| Enumerate every copy and every consumer | `compass:compass-map-relationships` | Collapsing N-1 of N copies is worse than collapsing none; the enumeration must be exhaustive before the first deletion |
| Pin the behavior all copies share | `superpowers:test-driven-development` | The shared contract is only observable while all copies still exist |
| Confirm no declared contract shifted | `confab:confab-contract-drift` | Consolidation silently changes which signature is authoritative |
| Prove the consolidated wire | `andon:andon-verify` | "All consumers still work" is a contract, and a green import is not evidence for it |

##### Enumerate before deleting

````prompt
"find every copy of this file and every place that references any of them — I want the complete list before we delete anything"
````

> Triggers `compass-map-relationships` — builds an indexed triple set over copies and
> consumers and traverses it hop by hop.

##### Pin the shared behavior first

````prompt
"before we collapse these copies, write tests that pin the behavior all of them share"
````

> Triggers `superpowers:test-driven-development` — the shared contract becomes executable
> while every copy is still present to check it against.

##### Prove every consumer still works

````prompt
"prove the wire: after consolidation, every consumer of the old copies still gets the same behavior"
````

> Triggers `andon-verify` — proves or refutes the stated consumer contract with
> reproduced evidence rather than a successful import.

**Worked example —** five plugins each carry a `scripts/build_symbol_index.py` that is
byte-identical to `tools/symbol-indexer/build_symbol_index.py` (all six share MD5
`1401d8e53d60aaffeab46c1d0cfc05b6`), and only the canonical copy has a test suite —
`tools/symbol-indexer/test_build_symbol_index.py`, which is what `plugin-checks.yml` runs.

### Migrate a return shape or type representation

Changing what a function hands back is a contract change wearing a refactor's clothes.
Every call site is a participant, and the compiler catches only the subset that is typed.

| Beat | Fires | Why here, not later |
|---|---|---|
| Judge the type before propagating it | `pr-review-toolkit:type-design-analyzer` (agent) | Rates encapsulation, invariant expression, and enforcement — cheapest before N call sites adopt the shape |
| Find every call site | `compass:compass-map-relationships` | An untyped or dynamically-dispatched call site is invisible to tooling and visible to an index |
| Detect declarations that no longer match usage | `confab:confab-contract-drift` | Type hints, signatures, docstring params, and schemas drift apart precisely during this migration |
| Prove old and new shapes are equivalent | `andon:andon-verify` | Equivalence is the contract; a passing suite is evidence only if the suite would notice |

##### Judge the new shape first

````prompt
"before we roll this new return type out everywhere, review its design — encapsulation, invariants, whether it's actually enforceable"
````

> Triggers `type-design-analyzer` — qualitative feedback plus ratings on encapsulation,
> invariant expression, usefulness, and enforcement.

##### Find every participant

````prompt
"find every call site that consumes this return value, including the dynamically-dispatched ones"
````

> Triggers `compass-map-relationships` — traverses the indexed call graph rather than
> trusting a single grep pattern.

##### Catch the declarations left behind

````prompt
"after the migration, check for drift between the declared signatures and how they're actually called"
````

> Triggers `confab-contract-drift` — reports every mismatch with both the declared and
> the actual-usage location.

**Worked example —** the `core.py` to `cli.py` boundary in
`tools/werkstoff-cli/src/werkstoff/`, whose output shape is pinned by the snapshot file
`tools/werkstoff-cli/tests/__snapshots__/test_cli.ambr` — snapshots that will re-record
silently if the migration lands before they are read.

### Same-stack version uplift

A same-stack uplift preserves code and tweaks it; it is not a rewrite from intent. The
right tool for it lives inside `code-modernization`, and the right way to use it is to
dispatch the one agent directly rather than adopt the eight-stage pipeline around it.

| Beat | Fires | Why here, not later |
|---|---|---|
| Identify the breaking changes that actually bite | `code-modernization:version-delta-analyst` (agent) | `modernize-brief.md:36` explicitly sanctions spawning this agent directly; the surrounding pipeline hard-refuses without artifacts this task has no reason to produce |
| Find the deprecated idioms against the targeted version | `self-assess:self-assess-code-idiom` | Judges idioms against the version the repo actually targets, not against the newest one |
| Re-check the manifests after the bump | `confab:confab-dependency-audit` | An uplift is when a plausible-but-nonexistent replacement package is most likely to be introduced |
| Apply the mechanical rewrites, one cluster at a time | `self-assess:self-assess-idiom-fix` | Dispatches one remediator per (file, kind) cluster, never a batch spanning files |

##### Get the deltas that matter here

````prompt
"we're moving this codebase up a major version of the same stack. Which breaking changes actually affect our code?"
````

> Dispatches `version-delta-analyst` directly — identifies the breaking changes between
> two versions of the same stack that bite this specific codebase, and drives the
> ecosystem's own migration tooling. No pipeline required.

##### Find idioms deprecated for the targeted version

````prompt
"find deprecated idioms in this repo, judged against the version we actually target — not the latest one"
````

> Triggers `self-assess-code-idiom` — detects the manifest's declared version per
> language and judges findings against it, with a separate Verify pass per candidate.

##### Apply the mechanical rewrites

````prompt
"apply the mechanical modernization fixes only — leave anything needing judgment for me"
````

> Triggers `self-assess-idiom-fix` — one remediator per file-and-kind cluster, scoped to
> already-verified modernization findings and nothing else.

**Worked example —** `tools/werkstoff-cli/pyproject.toml` declares
`requires-python = ">=3.12"` and `target-version = "py312"`, so any idiom finding must be
judged against 3.12 — flagging a pre-3.12 replacement as "modern" would be a regression
dressed as an uplift.

### Propagate a vendored artifact to N copies

Propagation is mechanical, parallel, and unforgiving: N-1 updated copies is a worse state
than zero updated copies, because the drift is now invisible.

| Beat | Fires | Why here, not later |
|---|---|---|
| Enumerate the copies and the canonical source | `compass:compass-map-relationships` | The count must be exhaustive before the first write; a missed copy is silent drift |
| Fan out one dispatch per copy, in one message | `superpowers:dispatching-parallel-agents` | Its own rule makes the difference explicit: multiple dispatch calls in one response run in parallel, one per response runs sequentially |
| Prove tree and lock agree afterwards | `andon:andon-verify` | The lock is the stated contract; a successful copy loop is not evidence that it holds |

##### Enumerate every copy

````prompt
"list every vendored copy of this artifact and the canonical source they're supposed to track"
````

> Triggers `compass-map-relationships` — an indexed enumeration of copies and their
> canonical source, traversed rather than recalled.

##### Fan the updates out at once

````prompt
"update all seven vendored copies in parallel — one agent per copy, all dispatched in the same message, mechanical tier model"
````

> Triggers `superpowers:dispatching-parallel-agents` — genuine parallel execution, with
> the model tier stated explicitly so the dispatch does not silently inherit the
> session's most expensive model.

##### Prove the lock still holds

````prompt
"prove the working tree now matches the committed artifact lock — strictly"
````

> Triggers `andon-verify` — treats lock-versus-tree agreement as the wire under proof and
> returns a structured verdict.

**Worked example —** `inline-d3.html` exists in the seven `plugins/*/assets/`
directories that carry one
plus the canonical `tools/d3-subset/inline-d3.html`, and CI already carries the proof
step: `plugin-checks.yml` runs `rrt artifacts --check --strict` specifically so a dropped
copy fails a job instead of denying an edit months later.

## Quality & verification

### Make a strategy enforced rather than documented

A rule that lives only in prose is a suggestion. This repo has measured the difference,
and the measurement is what makes the entry actionable rather than moralistic.

| Beat | Fires | Why here, not later |
|---|---|---|
| Derive one concrete, enforceable rule with evidence | `cupertino:cupertino-handbook-draft` | A rule stated abstractly cannot be mechanically checked; the draft step forces a real file:line basis |
| Measure current divergence from that rule | `cupertino:cupertino-handbook-check` | Enforcement written before the divergence is known will either block everything or nothing |
| Move the rule down the enforcement ladder | `plugin-dev:hook-development` | A `PreToolUse` hook holds regardless of model cooperation; prose does not |

##### Draft the rule with evidence behind it

````prompt
"turn this convention into one concrete rule with real file:line evidence — not a principle, a rule"
````

> Triggers `cupertino-handbook-draft` — dispatches one dimension analyst per named
> dimension to propose a single enforceable rule with cited evidence or an honestly
> labelled scaffolded default.

##### Measure the divergence

````prompt
"check these files against that rule and show me every divergence with a line number"
````

> Triggers `cupertino-handbook-check` — one drift auditor per named rule, with each
> candidate finding independently re-opened at its cited file:line before it is reported.

##### Move it from prose to a hook

````prompt
"prose isn't holding this. Write a PreToolUse hook that blocks it on the first attempt."
````

> Triggers `plugin-dev:hook-development` — guidance for hook events and the
> `${CLAUDE_PLUGIN_ROOT}` conventions, for the case where enforcement must not depend on
> the model reading the rule.

**Worked example —** the enforcement ladder measured in this repo's own `CLAUDE.md` —
prose in a `SKILL.md` as baseline, a guard behind a fenced `python3` block invoked one run
in three, a guard inside a Workflow script one in fourteen, and a `PreToolUse` hook of
`type: "command"` blocked on the first attempt. `tools/enforcement-audit/rules/` currently
holds a single `andon.json`; six plugins have no rules file at all.

### Oracle engineering and numerical V&V

Numerical correctness has a distinct failure mode: the code and the test agree because
both were written from the same misunderstanding. The fix is an oracle the implementation
did not author.

| Beat | Fires | Why here, not later |
|---|---|---|
| Ground the expected values in something external | `compass:compass-ground-evidence` | An expected value with no citation is a second implementation, not an oracle |
| Route the claim to numerical V&V | `andon:andon-verify` strategy b | Strategy b is "oracle-gap numerical V&V" — named for exactly the gap between a numeric claim and an independent source of truth |
| Check the assertions bracket real behavior | `confab:confab-assertion-audit` | A tolerance wide enough to pass is a tolerance wide enough to hide the defect |

##### Ground the expected values

````prompt
"where does each expected number in these tests come from? Cite a source for every one — no values derived from the code under test."
````

> Triggers `compass-ground-evidence` — refuses any factual claim without a file:line, a
> URL, or an explicitly flagged provisional basis.

##### Route it to numerical V&V

````prompt
"check whether this numeric claim is actually right — we have no independent oracle for it"
````

> Triggers `andon-verify` strategy b, oracle-gap numerical V&V — the strategy its
> classifier selects when the gap is between a numeric result and an independent source
> of truth.

##### Check the tolerance is not doing the work

````prompt
"are these numerical assertions tight enough to fail if the computation were subtly wrong?"
````

> Triggers `confab-assertion-audit` — proposes small perturbations and judges whether the
> existing assertions would catch them.

**Worked example —** `tools/symbol-indexer/test_build_symbol_index.py` is the suite CI
runs for the indexer; the oracle question is whether its expected index is derived
independently or regenerated from the same `build_symbol_index.py` it is meant to check.

### Whole-branch review without re-trusting the branch's own self-assessment

The failure mode is structural, not moral: a session that built something is the worst
available judge of it, because it reviews the intent it remembers rather than the diff it
produced. Every skill here is chosen for its blindness properties.

| Beat | Fires | Why here, not later |
|---|---|---|
| Dispatch a fresh reviewer against the diff range | `superpowers:requesting-code-review` | Dispatches a `general-purpose` subagent filling `code-reviewer.md` with BASE_SHA / HEAD_SHA — a reviewer that never saw the build session |
| Fan out the specialist passes in one message | `pr-review-toolkit:code-reviewer`, `pr-review-toolkit:silent-failure-hunter`, `pr-review-toolkit:pr-test-analyzer` (agents) | All six toolkit agents are diff-shaped and none fetches a PR itself; the caller passes scope, so they parallelize cleanly |
| Check declared contracts against real usage | `confab:confab-contract-drift` | Drops into a review gate with zero setup, and catches what a prose review reads past |
| Adjudicate the contested findings | `andon:andon-verify` | Its tribunal is explicitly "never authored or influenced by the session that proposed or built the fix under review" |

##### Dispatch a reviewer that never saw the build

````prompt
"request a code review of this branch against main — a fresh reviewer, not you, and give it the base and head SHAs"
````

> Triggers `superpowers:requesting-code-review` — dispatches a `general-purpose` subagent
> against an explicit BASE_SHA / HEAD_SHA range rather than against session memory.

##### Fan out the specialist passes

````prompt
"review this diff four ways in parallel — general correctness, silent failures, test coverage, type design. Most capable model for the whole-branch pass."
````

> Dispatches the `pr-review-toolkit` agents together in one message; the scope is passed
> in by the caller, since none of them fetches a pull request on its own.

##### Adjudicate what the reviewers disagree about

````prompt
"two reviewers disagree about whether this actually satisfies the requirement. Run the tribunal and decide it per criterion."
````

> Triggers `andon-verify` strategy a — defender and challenger dispatched blind and in
> parallel, a verifier reproducing the facts, and an adjudicator deciding per criterion
> against the stated contract.

**Worked example —** a branch touching all five plugin-local copies of
`build_symbol_index.py` plus `tools/symbol-indexer/` — a diff whose risk is entirely in
what it left out, which is precisely what a self-assessment cannot see.

### Incorporate external review feedback

**No werkstoff fit — this is pure Superpowers.** `superpowers:receiving-code-review` owns
this task end to end: reading feedback without defensiveness, separating what must change
from what is preference, and closing the loop. Werkstoff has no equivalent, and
`compass-draft-revise` — the nearest candidate — is scoped to scoring and revising a
*draft* against criteria, which fits a document under review and not a code branch. Using
it on code would be a force-fit.

| Beat | Fires | Why here, not later |
|---|---|---|
| Take the feedback on its own terms | `superpowers:receiving-code-review` | The instinct to defend is strongest immediately; the skill exists to interrupt it |
| Where the feedback is on a document, score and revise against criteria | `compass:compass-draft-revise` | Applies only when the artifact is prose; it rates 1-5 per criterion and revises only what falls at or below threshold |
| Confirm the loop actually closed | `superpowers:verification-before-completion` | "Addressed the comments" and "the comment's concern is gone" are different claims |

##### Receive it without defending

````prompt
"here's the review feedback. Work through it properly — separate what has to change from what's preference, and don't argue with the reviewer."
````

> Triggers `superpowers:receiving-code-review` — structured intake of external feedback,
> including the parts that are uncomfortable.

##### Revise a document against stated criteria

````prompt
"score this doc against the reviewer's criteria and fix only what falls below the bar"
````

> Triggers `compass-draft-revise` — rates 1-5 against each criterion, revises only what
> falls at or below threshold, reports exactly what changed, and caps at two revision
> cycles. Document artifacts only.

##### Confirm the concern is actually gone

````prompt
"for each review comment, show me the change that resolves it — not just that something changed nearby"
````

> Triggers `superpowers:verification-before-completion` — refuses a completion claim that
> rests on adjacency rather than resolution.

**Worked example —** applying a reviewer's finding to
`docs/plugin-authoring/references/craft-standards.md` is the document case where
`compass-draft-revise` genuinely applies; the same finding applied to a plugin's
`SKILL.md` behavior is a code change and belongs in the review entry above.

## Surface

### UI and design-system work

Design work has a hard ordering constraint that most other tasks do not: the principled
pass must precede the code, and the static audit must follow it. Running either in the
wrong order produces the appearance of both with the value of neither.

| Beat | Fires | Why here, not later |
|---|---|---|
| Convene the design council before any code | `cupertino:cupertino-council` | Its own frontmatter: "Always run before code, never after — retrofitting the council onto finished code defeats the purpose" |
| Build against the settled design | `frontend-design:frontend-design` | Implementation after the principles are settled, not in place of settling them |
| Audit the built surface statically | `self-assess:self-assess-ui-audit` | Accessibility, semantic markup, and hardcoded design values are only checkable once the markup exists |

##### Design before building

````prompt
"design this screen from first principles before we write any markup — I don't want something that just looks like every other AI-built page"
````

> Triggers `cupertino-council` — a five-voice design council convened at build-time,
> before any code, producing principled design plus a documented rationale.

##### Build against the settled design

````prompt
"now implement the design we settled on"
````

> Triggers `frontend-design` — implementation once the principles are fixed, rather than
> in place of fixing them.

##### Audit what was built

````prompt
"audit the UI we just built for accessibility, semantic markup, and hardcoded design values — statically, don't run the app"
````

> Triggers `self-assess-ui-audit` — a read-only static pass over JSX/TSX, Vue/Svelte,
> HTML, and CSS/SCSS, with a Verify pass per candidate finding.

**Worked example —** the HTML surfaces this repo already ships — the andon board viewer
built by `plugins/andon/scripts/build_board_html.py` and the branch-comparison viewer
built by `plugins/compass/scripts/build_branch_comparison_html.py` — checked against the
shared token set in `tools/design-tokens/tokens.css`.

### Documentation drift after a change

Docs drift is asymmetric: the code moves and the prose does not, so the drift is always in
the same direction and is never announced. The cheapest catch is a claim-level sweep
immediately after the change, while the diff is still legible.

| Beat | Fires | Why here, not later |
|---|---|---|
| Extract and verify every documentation claim | `self-assess:self-assess-docs-drift` | Verifies every extracted, in-scope claim against the current codebase; run months later it produces a backlog instead of a fix |
| Check the in-code comments too | `pr-review-toolkit:comment-analyzer` (agent) | Comments drift from the same edit as docs, and no docs sweep reads them |
| Survey the docs convention last | `codebase-consistency:pattern-analyst` (agent) | Genuinely post-hoc; a convention survey run before the content is correct clusters variants of the wrong text. Aligning what it finds is a whole task of its own — see `routing.md` |

##### Sweep the claims

````prompt
"we renamed several things this week — check whether the docs still describe what the code actually does"
````

> Triggers `self-assess-docs-drift` — dispatches verification for every extracted,
> in-scope documentation claim rather than reading the docs for plausibility.

##### Check the comments as well

````prompt
"check the comments in the files this change touched — are any of them now describing behavior that moved?"
````

> Triggers `comment-analyzer` — verifies comments against actual code behavior and flags
> comment rot as accumulating technical debt.

##### Survey the convention once the content is right

````prompt
"now that the docs are accurate, survey how docstrings are actually written across this repo and cluster the variants"
````

> Dispatches `pattern-analyst` — clusters the distinct approaches to one convention
> dimension with file:line evidence and a maturity read from git history. Acting on that
> survey is a separate task; see `routing.md`.

**Worked example —** this repo generates part of its own documentation surface:
`.rrt.toml` declares `[[tool.rrt.docs.shared_blocks]]`, which is what regenerates the
`rrt:auto:start:example-prompts-intro` block visible at the top of every plugin README's
Example Prompts section — so a drift sweep must distinguish generated prose from
hand-written prose before reporting either.

## How many plugins

The count follows the shape of the task, not the ambition of the prompt.

| Task shape | Plugins | Rationale |
|---|---|---|
| One clear feature | 2-3 | One before-code beat, one build beat, one gate. More beats than that spend attention on coordination rather than on the feature |
| A larger task | 4-5 | Enough for a scope beat, a mapping beat, a build beat, and two distinct gates that fail for different reasons |
| Genuinely parallel work | Split into independent workstreams | Each workstream carries its own 2-3 plugins |

For the parallel case, one condition is not optional: **the workstreams must not depend on
each other.** A workstream that waits on another's output is a sequential step wearing a
parallel label, and dispatching it in parallel produces a partial result that reads as a
complete one. Split on genuine independence — core implementation, tests and validation,
docs and rollout notes — or do not split at all.

Two mechanical rules govern the dispatch itself. From
`superpowers:dispatching-parallel-agents`: "Multiple dispatch calls in one response =
parallel execution. One per response = sequential." And from
`superpowers:subagent-driven-development`: "Always specify the model explicitly when
dispatching a subagent. An omitted model inherits your session's model - often the most
capable and most expensive - which silently defeats this section." Mechanical fan-out
takes the cheap tier, integration and judgment the standard tier, architecture and the
final whole-branch review the most capable tier, and any fix round that has already failed
three times moves at least one tier up.

Choosing *which* orchestrator owns a whole task — rather than which leaves fill a beat
inside one — is a separate question; see `routing.md`.
