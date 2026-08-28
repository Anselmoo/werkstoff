# Routing: which pipeline owns the task

Four pipelines can plausibly be pointed at the same repository — `code-modernization`,
`self-assess`, `codebase-consistency`, and `andon`. They look interchangeable from the
outside and are not. This reference decides between them, quotes the boundary the
plugins already declare themselves, and names the two overlaps that are real.

## The competition is at the brief, not the plugin

Installing all four is fine. Running two discovery passes is fine. The mutually
exclusive step is the **brief** — three of the four produce one, each is an approval
gate, and whichever one gets signed owns the rest of the session, because the executor
downstream reads that brief and treats its phases as entry criteria.

|Brief|Required inputs (refuses without them)|Phase ordering|
|---|---|---|
|`/modernize-brief`|`ASSESSMENT.md`, `topology.json`, `BUSINESS_RULES.md` — "If any are missing, say so and stop". Plus `DELTA_CATALOG.md` whenever the target is a newer version of the same stack|Target-architecture-first; enters plan mode as a human-in-the-loop gate|
|`self-assess-transform-brief`|`stage_graph.json`; without it the skill writes a "Ready-with-gaps" stub and stops. Structural decisions derive from `arch_health_summary.json` only|Leaf-first topological sort of the stage graph, work items ranked severity x complexity|
|`/consistency-brief`|`consistency.json`, `matrix.json`, `PATTERN_CARDS.md`/`CANON.json` — "If any are missing, say so and stop"|Dependency-first, then smallest blast radius first — stated explicitly as "not largest-first, unlike a legacy-modernization plan"|

The three orderings are not reconcilable. A leaf-first refactor plan, a
target-architecture rewrite plan, and a bank-the-small-wins alignment plan disagree
about what phase 1 is, by design. Pick the pipeline before the discovery pass, not
after.

One further hazard is worth stating without overclaiming: `code-modernization` and
`self-assess` both write a file named `MODERNIZATION_BRIEF.md`, with different
schemas, and no collision guard was found in either plugin. Treat a repo that has run
both as ambiguous until the file's provenance is confirmed by reading it. This is an
observed filename clash, not a documented conflict.

## Which pipeline owns the task

|Situation|Pipeline that owns it|What not to reach for, and why|
|---|---|---|
|Legacy or cross-stack rewrite — COBOL to Java, a monolith rebuilt on a new architecture|`code-modernization`: `/modernize-assess` -> `/modernize-map` -> `/modernize-extract-rules` -> `/modernize-brief` -> `/modernize-transform` or `/modernize-reimagine`|Not `self-assess-autopilot`. Its brief derives every `Keep`/`Merge`/`Split` decision from arch-health findings on the graph that exists today, so it can plan a refactor of the current system and never a rewrite from extracted intent|
|Same-stack version uplift — .NET Framework 4.8 to .NET 8, Java 8 to 21|`/modernize-uplift`, whose phase order comes from `DELTA_CATALOG.md`, because "an uplift's phase order is decided by its version deltas"|Not `self-assess-code-idiom`. It judges idioms against the language version the repo's manifest already declares, so it cannot plan a move to a version the manifest has not reached|
|Modern repo, unknown health, no specific complaint|`self-assess-autopilot` — CHECK, PLAN, approval gate, then FIX+VALIDATE handed to `andon-loop`|Not `/modernize-assess`. `code-modernization` assumes the code lives at `legacy/<system-dir>/` and is shaped for a legacy inventory and a steering-committee artifact; pointing it at a healthy modern repo produces a document nobody is going to approve|
|Modern repo that grew internally divergent — two or more valid, currently-used, undocumented ways of doing the same thing|`codebase-consistency`: `/consistency-scan` -> `/consistency-map` -> `/consistency-canonize` -> `/consistency-brief` -> `/consistency-align` -> `/consistency-verify`|Not `self-assess` and not `code-modernization`. Both classes of finding they own are declared out of scope here and actively routed out (see below), so running them for this produces the two categories `codebase-consistency` deliberately refuses to catalogue|
|One identified gap whose fix has to be proven, not asserted|`andon-loop`, or `andon-propose` and `andon-verify` standalone|Not a brief pipeline at all. None of the three briefs is reachable without its discovery artifacts, and none of them proves a fix; `andon` is the only family whose output is evidence rather than a plan|

## Where the boundary is already declared

`codebase-consistency` does not leave this to inference. Its README carries a section
titled "Scope — read this before installing both this and `self-assess`", which states
that the plugin does one specific thing "that a documented-convention checker and a
version-modernization checker structurally cannot": derive which variant becomes
canonical when two or more valid, currently-used, undocumented ways of doing something
coexist. It then routes the other two cases out by name:

> A convention already written down somewhere (`CLAUDE.md`, `house-rules.md`, a linter
> config, an ADR) is **out of scope** — that's a documented-convention auditor's job
> (e.g. `self-assess`'s `convention-auditor`).

> An idiom made obsolete by the language/framework version this codebase targets is
> **also out of scope** — that's version-driven modernization (e.g. `self-assess`'s
> `idiom-auditor` / `idiom-remediator`).

The routing is implemented, not just asserted. `/consistency-scan` emits
`out-of-scope-documented` and `out-of-scope-deprecated` records for those two
categories and does not detail them further — so a scan run alongside `self-assess`
hands back a list of what the other plugin should look at rather than a duplicate
finding set. The same section notes there is no hard dependency either way: the plugin
works standalone when neither neighbour is installed.

The genealogy is declared too. `codebase-consistency` states that it is a Derivative
Work, within the meaning of the Apache License 2.0, of Anthropic's
`code-modernization` plugin — the pipeline discipline, workflow-orchestration
mechanics (dependency-aware batching, circuit breaker, loop-until-dry extraction with
referee verification) and agent-boundary conventions originate there and are reused
under that licence, with the domain content rewritten for a different problem. That is
why the two command sequences rhyme: `preflight -> scan/assess -> map -> canonize/
extract-rules -> brief -> align/transform -> verify/harden`. Shared mechanics, different
problem. Do not read the resemblance as redundancy, and do not run both pipelines over
one area expecting them to agree.

## Two honest overlaps

Everything above separates cleanly. Two things genuinely do not.

**Same vocabulary, opposite direction.** `self-assess-code-idiom` and
`/modernize-uplift` both talk about deprecated idioms and version targets.
`self-assess-code-idiom` judges idioms against the version the manifest *already*
declares — it cleans up after a version moved. `/modernize-uplift` *performs* the
move, preserving structure and making "the smallest diffs that compile and behave
identically on the target", driven by the known breaking changes between source and
target. Running the auditor before the uplift measures the old world; running it after
is the correct use. A session that confuses the two will file a pile of findings that
the uplift was about to resolve anyway.

**Same extraction, different consumer.** `code-modernization`'s
`business-rules-extractor` and `self-assess-extract-rules` both mine calculations,
validations and state transitions into Given/When/Then rules with `file:line`
citations. The difference is what consumes the output: the former feeds
`BUSINESS_RULES.md`, a hard input to `/modernize-brief`, so that a rewrite can be
proven behaviour-equivalent; the latter loops to convergence and requires a two-judge
panel to confirm any P0 rule, and feeds a repo's own understanding of itself. Running
both over the same modules produces two rule sets that will not be reconciled by
anything. Choose by which brief, if any, is going to be signed.

## Use the agents without the pipeline

The most practical unlock in this document: `code-modernization`'s value is available
at a single beat without signing its brief. Six of its eight agents are standalone
leaves — `legacy-analyst`, `business-rules-extractor`, `version-delta-analyst`,
`architecture-critic`, `security-auditor` and `test-engineer`. Only `scaffolder` and
`uplift-migrator` are bound to the pipeline, because both write into
`modernized/<system>/` against an approved architecture.

The plugin sanctions this itself. `/modernize-brief` instructs that when the delta
catalog is missing, a session should either run `/modernize-uplift` through its
delta-catalog step "or spawn the **version-delta-analyst** agent directly — then
return here. Do not guess at the deltas."

##### Borrow one agent for one beat

````prompt
"spawn the version-delta-analyst agent directly on this repo and tell me which
breaking changes between our current runtime and the next LTS actually bite us —
don't start a modernization pipeline"
````

> Dispatches one `code-modernization` leaf into an otherwise unrelated session. The
> same shape works for `security-auditor`, `architecture-critic`, `legacy-analyst`,
> `test-engineer` and `business-rules-extractor`.

The equivalent holds on the werkstoff side: `andon-verify` and `andon-propose` both
state they never write to the ledger, so either one can be dispatched as a
verification or proposal beat inside another plugin's workflow without adopting
`andon`'s loop.

## Chain, do not choose

Two of these pipelines are not competitors in sequence, only in parallel.

A migration or an uplift is a **divergence generator**. `/modernize-transform` rewrites
from extracted intent and `/modernize-uplift` makes the smallest diffs that behave
identically on a new runtime — and both leave a codebase where the migrated modules
and the untouched ones now do the same thing two valid ways, with neither variant
written down as the standard. That is precisely the input condition
`codebase-consistency` exists for: N >= 2 variants, all still valid, none documented.

So the honest sequence after a completed migration is `/consistency-scan` over the
affected area, not another modernization pass.

This one is an **inference from the two scope statements, not a documented handoff**.
Neither plugin cross-references the other for this case, and nothing implements the
transition — no command emits a follow-up, and no artifact is shared. It is stated
here because the input condition matches exactly, and a reader who has just finished
an uplift should know what to point at next.
