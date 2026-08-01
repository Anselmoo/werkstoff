---
name: self-assess-transform-brief
description: This skill should be used after self-assess's finding skills have run, when the user asks to "synthesize the findings into a plan", "write the modernization brief", "what should we fix and in what order", or as the PLAN step of self-assess-autopilot. Synthesizes stage-map, arch-health, and every other domain summary into a phased, ranked, read-only transformation plan.
---

# self-assess-transform-brief

Synthesize every domain finding into MODERNIZATION_BRIEF.md: an ordered, ranked, executable
transformation plan. This skill never edits source code -- it only reads findings and writes
the plan.

## Step 0: Settings gate, then the stage_graph prerequisite

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/self_assess_cli.py check-enabled --repo <repo_root> --skill self-assess-transform-brief
```

Rule `transform-brief-gate-on-stage-graph`: if `<output_dir>/stage_graph.json` does not exist,
do NOT proceed with a real brief. Write a short `MODERNIZATION_BRIEF.md` and
`transform_brief_summary.json` noting "Ready-with-gaps -- run self-assess-stage-map first," and
stop.

## Step 1: Derive Keep/Merge/Split decisions from arch-health only

Read `arch_health_summary.json`. Every phase's structural decision (`Keep`, `Keep(1:1)`,
`Merge`, `Split`, `Layering-fix`) MUST derive from arch-health's findings -- never from a
freestanding architectural opinion formed here. No arch-health finding touching a stage means
that stage's decision is `Keep(1:1)`.

## Step 2: Order phases leaf-first

Topologically sort stages by the stage_graph so phases with the fewest dependencies come
first -- a stage nothing else depends on can move before a stage many things still import.

## Step 3: Attribute findings via the index lookup -- never re-derive

Rule `transform-brief-attributes-findings-via-lookup`: for every file:line finding from the
other domain summaries, look up its phase via `file_stage_index.json`, never by re-running the
package-boundary heuristic:

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/self_assess_cli.py attribute-citation --citation "<path:line>" --file-stage-index <path to file_stage_index.json>
```

If `file_stage_index.json` is absent, every attribution call returns `"Unattributed"` -- note
in the brief that attribution is unavailable this run, and file every finding under an
"Unattributed" section rather than guessing.

## Step 4: Rank work items by severity x complexity

Rule `transform-brief-work-item-ranking`:

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/self_assess_cli.py work-item-rank --severity High --complexity-weight <complexityByStage[stage] or omit for default 1>
```

`severity_weight` is fixed at High=3/Medium=2/Low=1; `complexity_weight` is that stage's index
from `complexity_score_summary.json` if `self-assess-complexity-score` has run, else the
default of 1. Sort each phase's work items by the returned rank, descending.

## Step 5: Route confab findings

If confab-plugin findings are present in any domain summary, route each by its `fixability`
field, not by re-reading its prose:

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/self_assess_cli.py route-confab-finding --finding <json finding>
```

`"advisory"` (only `fixability: "advisory"`) goes to the phase's Advisory notes; `"work_item"`
(no `fixability` key, or `fixability: "fixable"`) becomes a ranked work item per Step 4.

## Step 6: Flag P0 blockers

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/self_assess_cli.py flag-p0-blockers --rules <json list from business_rules_summary.json>
```

Any P0 rule with `confidence` other than `"High"` becomes a phase blocker -- record it in the
phase's Open Questions, not as an ordinary work item, since a low-confidence P0 business rule
means the phase risks breaking behavior nobody is sure about yet.

## Step 7: Write outputs

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/self_assess_cli.py validate-artifact --kind transform_brief_summary --file <path-or-inline-json>
```

Every phase requires `phase_number`, a `decision` from the fixed set, `open_questions`
(possibly empty), and `work_items` (ranked). Then resolve and write:

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/self_assess_cli.py resolve-output-path --repo <repo_root> --filename MODERNIZATION_BRIEF.md
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/self_assess_cli.py resolve-output-path --repo <repo_root> --filename TRANSFORM_SEQUENCE.mmd
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/self_assess_cli.py resolve-output-path --repo <repo_root> --filename TRANSFORM_MAPPING.mmd
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/self_assess_cli.py resolve-output-path --repo <repo_root> --filename transform_brief_summary.json
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/self_assess_cli.py resolve-output-path --repo <repo_root> --filename stage_map.json
```

`TRANSFORM_SEQUENCE.mmd` is a Mermaid graph of phase order; `TRANSFORM_MAPPING.mmd` maps old
stages to new ones per phase. Update `stage_map.json` with a `flows` field describing the
planned transformation, without altering its existing stage/wire data.

## Read-only constraint

This skill NEVER uses Edit and NEVER writes anywhere under source directories -- only the
plan artifacts listed above. It never edits source code, full stop.
