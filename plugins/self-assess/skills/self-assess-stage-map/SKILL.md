---
name: self-assess-stage-map
description: This skill should be used when the user asks to "map the repo's architecture", "show me the real module boundaries", "map stages and wires", or as the first step of self-assess-autopilot's CHECK phase. Extracts the real import/use graph per detected language, clusters files into stages by shallowest package boundary (never by manifest directory), and writes the full stage graph other self-assess skills depend on.
---

# self-assess-stage-map

Build the repository's real architectural map: stages (package/module boundaries) and wires
(the import/use edges between them), verified against actual source, not guessed from
directory names.

## Step 0: Settings gate

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/self_assess_cli.py check-enabled --repo <repo_root> --skill self-assess-stage-map
```

Stop on non-zero exit. Carry the returned `output_dir` and `skip_verification` through every
later step.

## Step 1: Detect languages

Reuse the same detection as preflight -- do not hand-roll a different threshold:

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/self_assess_cli.py detect-languages --manifests <json> --extension-counts <json>
```

## Step 2: Extract the import graph, one inline command per language

Dispatch the `stage-mapper` agent once per detected language. Each dispatch runs the
extraction as a **single inline read-only command** (e.g. a `grep -rn` / `rg` pass over
import statements, or a language-native AST dump), never by creating scratch files -- that is
the agent's own refusal, restated here so the calling skill does not ask for anything that
would violate it.

Cluster files into stages by the **shallowest importable package boundary** in each language
(the topmost directory that is itself an importable unit -- a directory with an `__init__.py`,
a `package.json`, a `go.mod`, etc.) -- never by "which directory does the manifest that covers
this file live in," which is wrong whenever two packages share one manifest.

## Step 3: Verify candidate wires

Unless `skip_verification` is true, verify every candidate wire (an edge between two stages) by
re-reading the actual import statement at its cited location before it is trusted -- do not
accept a wire based on the extraction pass alone. Label unverified findings per
skip-verification-behavior when `skip_verification` is true (no adversarial refutation, but
every finding still carries `verified: false`).

## Step 4: Write the full graph, never sampled

Rule `stage-graph-vs-stage-map-json` requires `stage_graph.json` to carry the *complete* edge
count, not a sample -- `self-assess-arch-health` depends on accurate fan-in/fan-out. Build it
with top-level `stages`, `wires` (every edge), `edgeCount` (== `len(wires)`), and `deadEnds`
(stages with no outgoing wires), then validate before writing:

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/self_assess_cli.py validate-artifact --kind stage_graph --file <path-or-inline-json>
```

The validator rejects the artifact outright if `edgeCount != len(wires)` -- a sampled edge list
cannot pass. The separate viewer-format `stage_map.json` (for STAGE_MAP.html) MAY sample down to
a handful of edges per stage for readability; only `stage_graph.json` carries this constraint.

## Step 5: Write file_stage_index.json -- deliberately partial

Rule `file-stage-index-partial-coverage`: this flat `{file: stage}` lookup MUST contain only
files that are BOTH an edge endpoint AND fall under a detected package boundary. A file that is
neither is absent by design -- do not backfill it with a guessed stage. Downstream consumers
(`self-assess-transform-brief`) treat a miss as `"Unattributed"`, never as an error; see
`attribute-citation` in the CLI for that exact lookup behavior.

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/self_assess_cli.py validate-artifact --kind file_stage_index --file <path-or-inline-json>
```

## Step 6: Resolve output paths and write

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/self_assess_cli.py resolve-output-path --repo <repo_root> --filename stage_graph.json
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/self_assess_cli.py resolve-output-path --repo <repo_root> --filename file_stage_index.json
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/self_assess_cli.py resolve-output-path --repo <repo_root> --filename stage_map_summary.json
```

Write `STAGE_MAP.md`, `STAGE_MAP.html` (a simple static graph render), `stage_graph.json`,
`file_stage_index.json`, and `stage_map_summary.json` to their resolved paths. `stage_map.json`
(viewer format, sampled edges) may also be written here for `self-assess-transform-brief` to
later append a `flows` field to.

## Read-only constraint

Never use Write/Edit for anything outside the resolved output paths above. The extraction
command dispatched to `stage-mapper` is read-only (grep/AST-dump), never a scratch file or a
mutation.
