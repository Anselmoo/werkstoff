---
name: andon-preflight
description: "Checks whether a repository is ready for andon-loop, andon-propose, or andon-verify without touching any files beyond testing ledger-directory writability. Use when the user asks if a repo is ready for andon, or before the first run of any andon skill in a new repository."
allowed-tools: "Read, Bash, Glob, Grep"
argument-hint: ""
---

# andon-preflight

Read-only readiness report. Never creates the ledger, never modifies files.

## Step 1: settings gate

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/andon_core.py load-settings <repo_root>
```

If the returned `enabled` field is `false`, **stop immediately** and report
"andon is disabled via .claude/andon.local.md" -- do not run any of the four
checks below.

## Step 2: run all four checks, always, even if one looks bad

Determine availability flags by inspection (do this yourself; the script
takes them as booleans since it has no way to query your installed agents):

- `--self-assess-stage-mapper` if the `self-assess:stage-mapper` agent resolves.
- `--confab-skill` if the `confab:confab-agentic-reliability` skill resolves.
- `--lsp-tool` if an `LSP` tool is available in this session.
- `--structural-index` if a Kythe/SCIP/LSIF index file exists on disk (check
  common locations with `Glob`, e.g. `**/*.kzip`, `**/compile_commands.json`,
  `**/*.lsif`).
- `--property-lib-python` / `--property-lib-js` / `--property-lib-other` if
  Hypothesis / fast-check / an equivalent appears in the repo's declared
  dependencies (check `pyproject.toml`, `requirements*.txt`, `package.json`).

Then:

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/andon_core.py preflight <repo_root> \
  [--self-assess-stage-mapper] [--confab-skill] [--lsp-tool] [--structural-index] \
  [--property-lib-python] [--property-lib-js] [--property-lib-other]
```

This runs **all four checks unconditionally** -- stage legibility, ledger
writability (via `mkdir -p` on the ledger's parent directory only, to test
writability, never creating the ledger itself), house-rules presence, and
cross-plugin availability -- and returns one JSON object matching the exact
schema: `stageLegibility`, `stageCountEstimate`, `ledgerDirWritable`,
`houseRulesPresent`, `crossPluginDependencies`, `verdicts`.

## Step 3: write the two outputs

1. `<output_dir>/PREFLIGHT.md` -- a status table plus verdicts, in prose,
   built from the JSON above. Before writing it yourself, confirm the path
   with `validate-write-path`, passing the path **relative to `repo_root`,
   already including the `output_dir` prefix** (not relative to
   `output_dir`) -- the third argument is the allowed directory the first
   argument must resolve inside of:

   ```
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/andon_core.py validate-write-path \
     <output_dir>/PREFLIGHT.md <repo_root> <output_dir>
   ```

2. `<output_dir>/preflight_summary.json` -- the exact JSON object from Step 2,
   unmodified (do not paraphrase or drop fields; the schema is load-bearing
   for `andon-status` and any external tooling that reads it later).

## Verdict semantics (already computed by the script -- report, don't re-derive)

- `andon-propose`: `Ready` if house-rules found, else `Ready-with-gaps`.
- `andon-verify`: `Ready-with-gaps` at minimum whenever a strategy
  prerequisite is missing, naming exactly which strategies degrade.
- `andon-loop`: `Not-ready` if the ledger directory isn't writable,
  `Ready-with-gaps` if topology detection would be heuristic/reduced, `Ready`
  otherwise.

Report all three plainly even if one is `Not-ready` -- deliver one complete
readiness report, not a halt at the first failing check.
