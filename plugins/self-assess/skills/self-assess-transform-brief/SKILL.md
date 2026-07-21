---
name: self-assess-transform-brief
description: Synthesizes self-assess-stage-map's graph, self-assess-arch-health's deficiency findings, the reporting domains' file:line findings (code-idiom/lint-audit/docs-drift), complexity-score's ranking, and extract-rules' P0/P1 rules into an executable transformation plan — a current-state → target-state component mapping (explicitly 1:1, merge, or split per stage), a phased leaf-first sequence, per-phase code-change work items (ranked by severity × complexity), and a per-phase behavior contract of business rules that must stay equivalent — plus Mermaid exports and a fed interactive walkthrough on the existing topology viewer. Use this when the user asks for a modernization brief, a transformation plan, a prioritized refactoring/remediation plan, whether to merge or split modules before a refactor, a phased migration sequence, or "what's the target architecture and how do we get there" for a live repo. NOT a re-derivation of the import graph (self-assess-stage-map builds that), NOT a deficiency finder (self-assess-arch-health), NOT itself a complexity ranking or finding scanner (it consumes those skills' sidecars, never re-derives them), and NOT a code-editing tool — this plan is read-only; executing it is a separate, explicitly-authorized step (self-assess-transform-execute).
---

Answer the question every other self-assess skill stops short of: **given
what's wrong, what's the plan?** This skill produces a `MODERNIZATION_BRIEF.md`
— modeled on `code-modernization`'s Brief format, retargeted at a live,
in-place repo instead of a legacy system slated for a rewrite — but it is
strictly **read-only**: it plans; it does not edit source, and it does not
enforce anything itself. A plan produced here is meaningful only once
something actually executes and gates it (see **Handoff**, below) — this
skill's job ends at a written, reviewable brief.

Scope boundaries, kept sharp:
- **vs `self-assess-stage-map`** — stage-map builds the import graph; this
  skill only *reads* `stage_graph.json`, never re-derives it.
- **vs `self-assess-arch-health`** — arch-health finds deficiencies
  (god-modules, cycles, layering violations) as pass/fail findings; this
  skill turns those findings into a *plan* (what to do about them, in what
  order) — it never re-runs the detection itself.
- **vs `self-assess-complexity-score`** — a complexity index is a ranking
  signal, not a target-state decision; this skill consumes it (as the
  cost-of-fix weight that orders work items within a phase, Step 3a) but
  never re-computes it.
- **vs the reporting domains** (`code-idiom`, `lint-audit`, `docs-drift`) —
  they *find* file:line issues; this skill *attributes* each to a phase (via
  `self-assess-stage-map`'s `file_stage_index.json`) and *sequences* it as a
  work item, never re-running the detection.
- **vs `self-assess-extract-rules`** — it mines the P0/P1 business rules;
  this skill turns them into a per-phase behavior contract (what must stay
  equivalent), never re-mining them.
- **vs `code-modernization`'s `modernize-brief`** — that command targets a
  legacy system under `legacy/$1` slated for a full rewrite (reimagine /
  transform / uplift). This skill targets the **same live repo** every other
  self-assess skill does — the plan it writes is for incremental,
  in-place change, not a parallel rebuild.

## Step 0 — Load settings and the graph

Read `.claude/self-assess.local.md` if it exists (see
`${CLAUDE_PLUGIN_ROOT}/references/settings.md`). If `enabled: false`, stop
and say so. Note `output_dir` (default `analysis/self-assess`).

`Read` `<output_dir>/stage_graph.json` (the full-graph sidecar
`self-assess-stage-map` writes — see that skill's SKILL.md). If it does
**not** exist, do not proceed with a real brief: write a short
`MODERNIZATION_BRIEF.md` and `transform_brief_summary.json` (empty) noting
**Ready-with-gaps — run `self-assess-stage-map` first**, and stop. This
mirrors the degrade path `self-assess-arch-health` uses for the same input.

Also `Read` `<output_dir>/file_stage_index.json` (the flat
`{"<file>": "<stage>"}` lookup `self-assess-stage-map` writes alongside the
graph). If it is **absent** (an older stage-map run predating this sidecar),
do not fail — proceed, but note in the brief that file:line findings could
**not** be attributed to phases this run (they all fall to the Unattributed
bucket, Step 3a), and to re-run `self-assess-stage-map` to enable
attribution.

## Step 1 — Load supporting findings and rules

`Read` whichever of these sidecars exist under `<output_dir>/`, skipping any
that don't (do not invent data for a skill that hasn't run):
`arch_health_summary.json`, `code_idiom_summary.json`,
`lint_audit_summary.json`, `docs_drift_summary.json`,
`ci_topology_summary.json`, `complexity_score_summary.json`,
`business_rules.json`, `ui_audit_summary.json`, and — if the `confab` plugin
has run in this repo — its four audit sidecars
`dependency_audit_summary.json`, `assertion_audit_summary.json`,
`contract_drift_summary.json`, `agentic_reliability_summary.json`.

**Two kinds of input, used differently — state this plainly in the brief:**

- `arch_health_summary.json`'s findings are **stage-scoped by construction**
  (a god-module/cycle finding's evidence names the stage(s) directly; a
  layering finding names the wire). These drive the current→target **mapping
  decision** in Step 2 — Keep/Merge/Split.
- The **finding domains** each carry a `findings` array whose entries are
  **file:line-scoped** and share one contract — `{severity, title, evidence,
  category}` (self-assess's own `code_idiom`/`lint_audit`/`docs_drift`, the
  new `ui_audit`, and confab's four audits), the last of which additionally
  carry a `fixability` of `"fixable"` or `"advisory"`. The location lives in
  `evidence` (or `codeEvidence` for docs-drift) — a repo-relative `path:line`
  optionally followed by `: snippet`. These do **not** change the mapping
  decision, but — new in this skill — they are attributed to phases as
  concrete **work items** (Step 3a) via the `file_stage_index.json` lookup:
  parse the leading `path` out of the evidence string (everything before the
  last `:<digits>`), look it up in the index to get its stage, and place the
  finding in that stage's phase. This is a **lookup, not a re-derivation** —
  `self-assess-stage-map` already owns the package-boundary heuristic and now
  publishes its result, so the objection that once kept these findings out of
  the plan no longer applies. **Fixability routing:** a finding carrying
  `fixability: "advisory"` (confab's weak-assertion and agentic-redesign
  findings) is **never** rendered as an auto-actionable work item — it goes
  into the phase's **Advisory notes** list (Step 3a). Findings with no
  `fixability` key (self-assess's own domains + `ui_audit`) and confab
  findings with `fixability: "fixable"` become work items as normal.
- `complexity_score_summary.json`'s `complexityByStage` is the **ranking
  signal** (Step 3a): the per-stage relative index that, multiplied by a
  finding's severity, orders work items within a phase (highest-debt ×
  highest-severity first). It is not a finding and never appears as a work
  item itself.
- `business_rules.json`'s P0/P1 rules become the **Behavior Contract**
  (Step 3b), attributed to phases through the same index lookup on each
  rule's `source` location.

## Step 2 — Derive the current → target mapping (deterministic, from arch-health only)

For each stage in `stage_graph.json`, decide exactly one of **Keep (1:1)**,
**Merge**, or **Split**, driven only by whether an arch-health finding
touches it:

- A stage named in a `god-module` finding → **Split**. This skill does not
  invent sub-component names or boundaries — that's a design judgment call,
  not a mechanical derivation. Record it as an **Open Question**: "Split
  `<stage>` — by what responsibility boundary? (arch-health's finding:
  `<description>`)".
- A stage named in a `cycle` finding (a strongly-connected component) →
  **Merge** the cycle's members into one target component, by default —
  but also record an **Open Question** offering the alternative
  (break the cycle instead of merging, e.g. via dependency inversion or
  extracting the shared contract), since which resolution is correct is a
  domain call this skill cannot make from the graph alone.
- A stage named as the `from` or `to` of a `layering-violation` finding →
  **Keep (1:1)**, but flag the specific wire as an Open Question: move the
  shared code out of the test/scaffold stage, or invert the dependency.
- Every other stage → **Keep (1:1)**. No open question.

A stage can accumulate more than one finding (e.g. a god-module that's also
mid-cycle); if so, its decision is the more disruptive of the two
(Split/Merge > Keep) and both open questions carry forward.

## Step 3 — Derive the phased sequence (deterministic, from stage_graph.json's wires)

Order stages **leaf-first** (mirrors `code-modernization`'s
"build-graph leaf-first" doctrine for same-stack, in-place work — the
lowest-risk, fewest-dependencies-first ordering): treat each wire
`{from, to}` as "`from` depends on `to`". Run a topological sort (Kahn's
algorithm) where a stage becomes eligible once every stage it depends on
(every `to` reachable from its outgoing wires) is already placed. Stages
that become eligible in the same round form one **phase** (a wave — they
have no ordering constraint relative to each other, so they can proceed in
parallel). A cycle's member stages are placed together in the same phase as
a group (their mutual dependency makes them inseparable until the Step 2
Open Question about the cycle is resolved) — never silently broken into two
phases by picking an arbitrary edge to ignore.

Each phase gets: the stages in it, its target-mapping decisions (from
Step 2), and — if any member stage has an unresolved Open Question — a note
that the phase's entry criteria include resolving it first.

## Step 3a — Attach file:line findings as per-phase work items (the bridge)

This is what turns the plan from a module-reshuffle into an actionable
code-change plan: the finding domains' file:line findings become concrete
work items, attributed to the phase whose stage owns their file.

For every finding in each loaded finding domain — self-assess's own
`code_idiom`, `lint_audit`, `docs_drift`, and `ui_audit`, plus confab's
`dependency_audit`, `assertion_audit`, `contract_drift`,
`agentic_reliability` if present:

1. **Extract the file path.** From the finding's location string (`evidence`,
   or `codeEvidence` for docs-drift), take everything before the **last**
   `:<digits>` occurrence as the repo-relative `path`, and those digits as
   `line`. (Format is `path:line` optionally followed by `: snippet`.)
2. **Route by fixability.** If the finding carries `fixability: "advisory"`
   (confab's weak-assertion and agentic-redesign findings), it is **not** a
   work item — attribute it (step 3) and place it in that phase's **Advisory
   notes** list instead, then skip steps 4–5 for it. All other findings
   (no `fixability` key, or `fixability: "fixable"`) are work items.
3. **Look up the stage.** `stage = file_stage_index[path]`. If `path` is not
   a key (an isolated file with no import edges, or the index was absent),
   the finding is **Unattributed** — collect it for the Unattributed bucket
   (Step 4 §Work Items), never silently drop it. (Advisory findings that are
   unattributed go to an Unattributed advisory note, same principle.)
4. **Attribute to the phase** that placed `stage` in Step 3.
5. **Rank within the phase.** Score each work item
   `severity_weight × complexity_weight`, where `severity_weight` is
   High=3 / Medium=2 / Low=1 (from the finding's `severity`), and
   `complexity_weight` is `complexityByStage[stage]` from
   `complexity_score_summary.json` (default 1 if complexity-score hasn't run
   or the stage is unscored). Higher score first — the technical-debt
   prioritization ordering (severity × cost-of-fix). Ties keep input order.

A work item's rendered line is:
`<severity> · <domain> · <file:line> — <finding title/description> (suggestedFix if present)`.
Do **not** invent fixes beyond what the finding already states — copy its
`title`/`description`/`suggestedFix` through; this skill plans, it does not
design. Tag each work item's `<domain>` with its source (e.g. `code-idiom`,
`ui-audit`, `confab:contract-drift`) so an executor knows which fix skill
owns it (`self-assess-idiom-fix`, `self-assess-transform-execute`, or
`confab`'s `confab-remediator`).

## Step 3b — Derive the per-phase Behavior Contract (from business_rules.json)

If `business_rules.json` was loaded, for each **P0 or P1** rule: extract the
file `path` from its `source` (same last-`:<digits>` rule as Step 3a), look
up its stage in `file_stage_index.json`, and attribute the rule to that
stage's phase. A rule whose file isn't in the index is Unattributed — list
it in the contract under an explicit "unattributed rules" note (the phase
that touches that code must still honor it).

For each attributed rule, record its **validation strategy** by category:
`Calculation` / `Lifecycle` → **characterization tests** (pin the current
input→output / state-transition behavior before the phase's changes);
`Validation` / `Policy` → **contract tests** (assert the rule's pass/fail
condition still holds at its boundary). A **P0 rule with `confidence` below
High is a phase blocker** — the phase's entry criteria must include a human
confirming the rule before any code in that phase changes (mirrors
`code-modernization` Brief §5). This skill only *states* the obligation; the
proof runs later, in andon-verify (see **Handoff**).

## Step 4 — Write the brief

Create `<output_dir>/MODERNIZATION_BRIEF.md`, modeled on
`code-modernization`'s Brief sections but trimmed to what this skill can
actually derive (no business-walkthrough/persona section — self-assess has
no persona concept, same honesty `self-assess-stage-map` already applies to
its own `flows`):

1. **Objective** — one paragraph: current state (stage/wire counts from
   `stage_graph.json`, aggregate finding counts from Step 1's sidecars,
   naming the worst arch-health severity present), why now.
2. **Target mapping** — a table, one row per stage: `Stage | Decision
   (Keep/Merge/Split) | Why (the arch-health finding, or "no deficiency
   found") | Open Question (if any)`.
3. **Phased sequence** — one subsection per phase, each containing:
   - stages in it, entry criteria (upstream phases' stages placed, any Open
     Question resolved, **any P0-blocker rule from §5 confirmed**), exit
     criteria (the specific arch-health finding(s) this phase's decision
     addresses no longer apply — re-run `self-assess-arch-health` to confirm).
   - **Work Items** (from Step 3a) — the phase's file:line findings grouped
     by stage, ranked by severity × complexity, each as the rendered line
     from Step 3a. If the phase has none, say "no file:line findings
     attributed." At the end of §3 overall, an explicit **Unattributed
     findings** bucket lists every finding whose file wasn't in the index
     (with why: isolated file / index absent) — nothing is silently dropped.
   - **Advisory notes** (from Step 3a's fixability routing) — the phase's
     `advisory` findings (confab weak-assertion / agentic-redesign): listed
     as human-judgment items, explicitly **not** auto-actionable work items.
     Omit the subsection if the phase has none.
   - **Behavior Contract** (from Step 3b) — the P0/P1 rules this phase must
     keep equivalent, each with its validation strategy, P0-blockers marked.
4. **Best-practice rationale** — name the doctrines actually applied:
   leaf-first/topological phase ordering, severity × complexity work-item
   prioritization (technical-debt cost-of-fix ranking), the
   characterization-vs-contract validation split, and — only if the graph
   contains a cycle finding — the specific tradeoff between merge-to-resolve
   and break-the-cycle (dependency inversion / extract-shared-contract),
   citing why each is a legitimate option rather than picking one silently.
5. **Open Questions** — every one flagged in Steps 2–3b (including each
   P0-blocker rule needing human confirmation), collected in one place as an
   approver checklist (mirrors `code-modernization`'s Brief §7).

This skill produces **no Approval Block and stops no loop itself** — see
**Handoff**, below, for what happens after the brief is written.

Also write `<output_dir>/transform_brief_summary.json`:
`{"stagesAnalyzed": N, "phaseCount": N, "decisionCounts": {"keep": N,
"merge": N, "split": N}, "openQuestions": N, "workItemCount": N,
"advisoryNoteCount": N, "unattributedFindings": N,
"behaviorContractRules": N, "p0Blockers": N}`
(`workItemCount` = attributed fixable file:line findings; `advisoryNoteCount`
= attributed `advisory`-fixability findings; `unattributedFindings` = those
with no stage; `behaviorContractRules` = P0/P1 rules attributed; `p0Blockers`
= P0 rules with confidence below High). Like
`self-assess-complexity-score`, this is excluded from the graded
severity/category dashboard (`self-assess-status`'s combined JSON, the
`findings-dashboard.html` `DOMAINS` registry) — a transformation plan isn't
a pass/fail finding, it's a plan. `self-assess-status` still lists its
artifacts in the inventory table.

## Step 5 — Mermaid exports

Write two small, diffable `.mmd` files to `<output_dir>/` — the lightweight,
GitHub-rendering counterpart to the heavier interactive viewer (matching
`code-modernization`'s own split between small exportable `.mmd` artifacts
and its one big `topology-viewer.html`; this repo has never emitted Mermaid
before this skill):

- `TRANSFORM_SEQUENCE.mmd` — `flowchart LR`, one node per phase
  (`Phase N: <stage, stage, ...>`), edges `Phase N --> Phase N+1` in order.
- `TRANSFORM_MAPPING.mmd` — `graph TD`, one node per stage labeled with its
  decision (`<stage> (Keep|Merge|Split)`), grouped via `subgraph` by
  decision type. No `gantt` chart — like `modernize-brief`, this plan makes
  no calendar-time claims, only sequencing ones.

Keep both under ~40 edges (code-modernization's own cap for readability); if
the stream is larger, note in the brief that the Mermaid exports are
phase-level summaries, not the full per-file graph (`STAGE_MAP.html` already
covers that).

## Step 6 — Feed the topology viewer's dormant flow walkthrough

`self-assess-stage-map` writes `stage_map.json` with `flows: []` always —
by its own admission, stage-map "has no persona-walkthrough concept." This
skill is what that dormant feature was always waiting for: the phase
sequence *is* a walkthrough, just not a persona one.

Read `<output_dir>/stage_map.json`, replace only its `flows` field (leave
every other field — `root`, `edges`, `deadEnds`, `observations` — exactly
as `self-assess-stage-map` wrote them), and re-`Write` it:

```json
"flows": [
  { "name": "Transformation sequence", "persona": null,
    "steps": [
      { "label": "Phase 1: <stage, stage>", "nodes": ["stage:<name>", "stage:<name>"] },
      { "label": "Phase 2: <stage>",        "nodes": ["stage:<name>"] }
    ] }
]
```

`nodes` must be existing node `id`s from `stage_map.json`'s tree — use the
stage-level `stage:<name>` ids (the same ids `deadEnds` already matches
against), not file-level ids, since a phase operates at stage granularity.
Then re-run the injection script so the viewer picks it up:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/self-assess-stage-map/scripts/render_stage_map.py" \
  "${CLAUDE_PLUGIN_ROOT}/assets/topology-viewer.html" <output_dir>
```

If `stage_map.json` doesn't exist (shouldn't happen if Step 0's
`stage_graph.json` check passed, since both are written by the same
`self-assess-stage-map` run, but don't assume), skip this step and note in
the brief that the interactive walkthrough isn't available this run.

## Handoff (read-only — this skill does not execute the plan)

This skill's plan becomes actionable only through a separate, explicitly-
gated skill: **`self-assess-transform-execute`**. That skill applies exactly
one phase's code changes via the `transform-executor` agent — the only
Edit/Write-capable agent in this plugin — and only when the repo owner has
set `transform.mode: execute` and listed that specific phase number in
`transform.authorized_phases` (see `references/settings.md`); it refuses
outright in the default `plan` mode, and refuses a phase whose Open
Questions aren't resolved by a human first. It also never verifies its own
output — its last step is always an explicit hand-off to `andon-verify`'s
adversarial tribunal (independent Defender/Challenger/Verifier agents, never
a same-session self-review), or to `andon-loop` if the user wants the
phase's proof and record-keeping to live in andon's OKF ledger.

This three-skill separation — `self-assess-transform-brief` (plans, always
read-only) → `self-assess-transform-execute` (applies one authorized phase,
the plugin's one Edit exception) → `andon-verify` (proves it, never the
same agent that made the change) — exists because a Merge or Split decision
is a `hard-to-reverse`-or-higher change, and confidence in this plugin's
otherwise-100%-read-only safety model depends on that boundary never being
blurred into a single self-checking step.

## Present

Report: stage count, phase count, decision counts (keep/merge/split), open
question count. If any Split or Merge exists, name the first phase that
contains one — that's the one most worth discussing before anything is
executed. Suggest: `glow -p <output_dir>/MODERNIZATION_BRIEF.md`, and that
opening `<output_dir>/topology-viewer.html` now shows the transformation
sequence as a selectable flow.
