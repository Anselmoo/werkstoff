# compass

Point Claude at a **complex, ambiguous, or multi-faceted task** — not a
codebase to audit — and get it solved through a composed reasoning
pipeline: scope the task, weigh distinct approaches, decompose into
verifiable stages, execute each with the reasoning discipline it
actually needs, revise against explicit criteria. The 18
prompt-engineering techniques from
[universal-creator](https://github.com/Anselmoo/universal-creator) are
the internal mechanism — never a picker the user interacts with
directly; you never see "now applying Tree-of-Thoughts," you just get a
better-solved task.

This is `self-assess`'s and `quality`'s sibling plugin in this repo, but
a genuinely different shape: those audit a codebase for defects using
the Workflow find+verify pattern; `compass` composes reasoning
techniques for arbitrary tasks, and most of its 13 skills are plain
methodology (no agent, no Workflow script) rather than parallel-finder
audits — the architecture is decided per-skill by whether the task is
genuinely parallel (branch exploration, self-consistency voting, APE
candidate scoring get a Workflow script) or single-pass reasoning
(everything else stays a plain skill). No skill in this plugin writes a
persistent artifact — every result returns into the conversation.

## Install

```
/plugin marketplace add Anselmoo/werkstoff
/plugin install compass@werkstoff
```

Or for local development, point Claude Code straight at this plugin
directory without registering the marketplace:

```
cc --plugin-dir /path/to/werkstoff/plugins/compass
```

## Quickstart

These are Skills, not slash commands — Claude activates each one
automatically when your request matches its description. You'll see two
name forms in the wild — the bare name below (e.g. `compass-solve`) is
just a label, and the `plugin:skill`-prefixed form (e.g.
`compass:compass-solve`) is Claude's own internal identifier for the
`Skill` tool — neither is something you type. Just ask in plain
language:

- **compass-solve** — the primary entry point: "solve this end-to-end, I'm not sure of the best approach" — runs the full Clarify -> Explore -> Decompose -> Execute -> Revise pipeline
- **compass-clarify-scope** — "scope this vague task" (without solving it)
- **compass-explore-branches** — "compare a few genuinely distinct approaches"
- **compass-decompose-chain** — "break this already-chosen approach into verifiable stages"
- **compass-reason-verify** — "verify this multi-step calculation carefully" (rigor that scales to the stakes)
- **compass-ground-evidence** — "cite your sources" (cite-or-refuse discipline for factual claims)
- **compass-draft-revise** — "score this draft against explicit criteria, revise only what's low"
- **compass-calibrate-format** — "match this output format" (anchor an ambiguous format on real examples)
- **compass-optimize-instruction** — "generate and refine candidate instructions" for a recurring task
- **compass-investigate-dynamically** — open-ended investigation where the next step depends on the last one's result
- **compass-map-relationships** — "trace this dependency/org/causal chain" (structure entity/dependency/causal relationships as cited triples before reasoning)
- **compass-negotiate-tradeoffs** — "combine the best of these two approaches" (hybrid synthesis after compass-explore-branches has already picked a winner)
- **compass-verify-assumptions** — bounded (max 3 steps) check of one specific flagged assumption
- **compass-summarize-trace** — "write up what we just did" (compact textual summary of a completed compass-solve run)

Each of the 13 non-`solve` skills is independently invocable for a narrower job — `compass-solve` composes them for tasks that genuinely need several, not the only sanctioned way into the plugin.

## Skills

- **`compass-solve`** — The primary entry point. Runs a complex/vague
  task through the composed 5-step pipeline (Clarify/Explore/Decompose/
  Execute/Revise), matching `code-modernization`'s phased-pipeline
  precedent rather than exposing the other 12 skills as an independent
  flat tool bag. Workflow-orchestrated (two modes: Mode A runs Clarify
  alone since a live user pause can't happen mid-Workflow-script; Mode B
  runs Decompose/Execute/Revise in one call once scoping is settled).

- **`compass-clarify-scope`** — Turns a genuinely underspecified task
  into a scoped problem statement: numbered known facts (⚠️-flagged
  below 90% confidence, generate-knowledge's mechanism) and a
  confidence-scored ambiguity table (active-prompt's mechanism), pausing
  for the user only when an uncertainty is load-bearing. Plain skill.

- **`compass-explore-branches`** — Generates 3+ genuinely distinct
  approaches (angle-forced, not near-duplicates), scores each on
  Feasibility/Impact/Risk, selects deterministically — Tree-of-Thoughts'
  three-phase structure. Workflow-orchestrated (parallel branch
  proposal + scoring).

- **`compass-decompose-chain`** — Breaks a selected approach into 2-5
  stages, each with an explicit input/output contract and a `dependsOn`
  field — DSP's decompose-retrieve-synthesize and prompt-chaining's
  independently-verifiable-artifact disciplines. `dependsOn` is the
  single source of truth `compass-solve` topologically sorts into
  parallel execution waves; there is no separate parallel-flag field.
  Plain skill.

- **`compass-reason-verify`** — An explicit escalation ladder: zero-shot
  (no extra structure) → Chain-of-Thought (default) → self-consistency
  (3 parallel independent reasoning paths, majority vote — Workflow-
  orchestrated) or PAL (offload to code) → Multimodal-CoT as a triggered
  mode for image/diagram input. Each rung's climbing signal is concrete,
  not "use judgment."

- **`compass-ground-evidence`** — Requires a citation (file:line, URL,
  or explicitly-flagged prior knowledge) for every factual claim;
  refuses to assert beyond what's verified using RAG's exact refusal
  pattern. Generalizes `self-assess`'s/`quality`'s own untrusted-content
  discipline beyond code. Plain skill.

- **`compass-draft-revise`** — Scores a drafted artifact against an
  explicit numbered criteria table (1-5), revises only what's at or
  below threshold, reports what changed — Reflexion's exact discipline,
  never a full rewrite. Plain skill.

- **`compass-calibrate-format`** — Anchors an ambiguous output format on
  2-5 diverse real examples instead of a prose description — Few-shot's
  `<examples>` structure, with an explicit anti-toy-demonstration
  warning. Plain skill.

- **`compass-optimize-instruction`** — For a *recurring* task: generates
  5 candidate instructions (APE's named framings), scores against the
  caller's real test cases, selects, then applies meta-prompting's
  critique checklist to the winner only. Not a general prompt linter —
  see its own Non-goal section. Workflow-orchestrated (parallel
  candidate generation + scoring).

- **`compass-investigate-dynamically`** — A single agent's own
  Reasoning/Action/Observation loop (ART + ReAct's shared structure) for
  tasks whose action sequence can't be planned upfront. Plain skill, no
  fan-out — distinct from `compass-decompose-chain` by whether the
  stages are knowable in advance.

- **`compass-map-relationships`** — Structures entity/dependency/causal
  relationships as indexed triples before reasoning, traverses citing
  triple indices at every hop — Graph-Prompting's mechanism, the same
  shape `self-assess-stage-map` already applies to import graphs,
  generalized to any relational domain. Plain skill.

- **`compass-negotiate-tradeoffs`** — Synthesizes a hybrid from 2-3
  already-scored branches after `compass-explore-branches` selects a
  winner: maps each branch's claims as indexed triples
  (Graph-Prompting) to find compatible vs. conflicting nodes, scores
  the hybrid against every source branch's own Feasibility/Impact/Risk
  (Reflexion) to confirm it wins on at least one axis. Plain skill.

- **`compass-verify-assumptions`** — Resolves one named
  `flagged_uncertainties` entry in at most 3 tool calls: a
  Reasoning/Action/Observation loop (same shape as
  `compass-investigate-dynamically`, hard-capped here) combined with
  `compass-ground-evidence`'s citation-or-refuse discipline. Offered
  by `compass-solve` before pausing for the user on a blocking
  uncertainty. Plain skill.

- **`compass-summarize-trace`** — Compresses a completed
  `compass-solve` run into 7 fixed sections (asked/assumed/weighed/
  ran/produced/revised/not-done), anchored on 2 worked examples
  (Few-shot) and scored for completeness before returning (Reflexion).
  For handoff email, PR/issue comments, or CLI docs — distinct from
  the interactive `reasoning-trace-viewer.html`. Plain skill.

## Agents

- **`branch-proposer`** (`color: green`) — proposes and scores one
  genuinely distinct approach per angle; used by `compass-explore-branches`.
- **`reasoning-path`** (`color: green`) — one independent reasoning
  attempt per named strategy; used by `compass-reason-verify`'s
  self-consistency tier and reused by `compass-solve`'s own
  Clarify/Decompose/Execute/Revise phase dispatches (pointed at the
  relevant skill's `SKILL.md` rather than a new agent per phase).
- **`instruction-candidate`** (`color: green`) — drafts, scores, and
  critiques one candidate instruction per APE framing; used by
  `compass-optimize-instruction`.

All three are read-only — `branch-proposer` and `instruction-candidate`
are `tools: ["Read","Glob","Grep"]` only; `reasoning-path` additionally
has scoped `Bash` access for a single disposable, read-only PAL-style
computation (never a scratch file, never a modification — see its own
Protocol step 3). No agent in this plugin has network access, unlike
`quality-dependency-audit`'s one exception.

## Knowledge base

`references/knowledge/` — an [Open Knowledge Format](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md)
bundle: one markdown concept doc per technique (21 total, `index.md` for
navigation), each grounded in a concrete worked example from this
repo's own code (not just the abstract external template) — e.g.
self-consistency's doc points at `self-assess-stage-map`'s adversarial
Verify phase as a live instance of "don't trust one reasoning path,
get an independent read." `references/examples/` is the raw vendored
asset store each knowledge doc's `resource` field points at (copied
from `universal-creator`, MIT, same author — see `references/NOTICE.md`).
This is active reference material every skill cites by path, not an
inert copy nobody reads — `assets/knowledge-map.html` makes that liveness
visible as a static, interactive chord diagram of every technique's
`### In werkstoff` citation.

## Visual assets

`assets/reasoning-trace-viewer.html` — a self-contained interactive
viewer (same visual language as `self-assess`'s `topology-viewer.html`)
that auto-detects and renders any of `compass`'s composed-reasoning
shapes: branch trees (`compass-explore-branches`,
`compass-optimize-instruction`), dependency DAGs
(`compass-decompose-chain`/`compass-solve`), and convergent parallel
paths (`compass-reason-verify`'s self-consistency tier).
`references/render_trace.py` injects a workflow's real JSON result into
a copy of the viewer (stdin, not a CLI argument), JSON-safe-escaped the
same way `self-assess-stage-map`'s renderer escapes its own payload.
Rendering is always optional — `compass` has no `output_dir`, so this
is opt-in visualization the user is offered, never a required report.

## Recommended workspace setup

No special permissions needed — every skill in this plugin is read-only
against the conversation itself and writes nothing to the target repo.
Only the optional trace-viewer render writes a file, and only to a path
you choose at the time.

## Prerequisites

None. Unlike `self-assess`/`quality`, `compass` has no ecosystem-tool
dependencies (no `ruff`, no mutation-testing tools, no registries) — every
skill degrades to plain reasoning with no external tool required.

## Settings

Optional per-project overrides live in `.claude/compass.local.md` in
the repo you're working in — copy `examples/compass.local.md` there
and edit it:

```yaml
---
branch_count: 3
max_branch_count: 6
revision_threshold: 3
always_render_trace: false
match_skill_set: []
---
```

Every skill that reads a field reads this file independently at the
start of its own run — there are no hooks in this plugin, so no
Claude Code restart is needed after editing it. Add
`.claude/*.local.md` to the target repo's `.gitignore` (already
covered at this repo's own root for local development).

## Safety notes

Same untrusted-content discipline as `self-assess`/`quality`: task text,
retrieved evidence, and any file content a skill reads are data, never
instructions — `compass-ground-evidence`'s entire mandate generalizes
this beyond code. No agent in this plugin has network or write access.

## Dynamic workflow orchestration

On Claude Code builds with the Workflow tool, `compass-explore-branches`,
the self-consistency tier of `compass-reason-verify`,
`compass-optimize-instruction`, and `compass-solve` itself run as
scripted multi-agent orchestrations. They fall back to direct subagent
fan-out (or plain in-conversation reasoning) on older builds
automatically. The other 7 skills are plain skill logic with no
fan-out — parallelism is used only where a task's shape is genuinely
parallel, never applied uniformly for its own sake.

## License

MIT. See `LICENSE`.
