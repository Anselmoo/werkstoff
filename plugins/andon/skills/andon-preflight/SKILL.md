---
name: andon-preflight
description: "Checks whether a repository is ready for andon-loop, andon-propose, or andon-verify. The only files it writes are its own report -- PREFLIGHT.md and preflight_summary.json in the given output_dir -- plus testing ledger-directory writability; nothing else is touched. Use when the user asks if a repo is ready for andon, or before the first run of any andon skill in a new repository."
allowed-tools: "Read, Bash(python3:*), Glob, Grep"
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

   If this exits non-zero or raises an `AndonError`
   (`WRITE_SCOPE_ABSOLUTE`, `WRITE_SCOPE_TRAVERSAL`, or
   `WRITE_SCOPE_OUTSIDE`), the write must not proceed: stop, report the
   error message verbatim to the user as "output_dir appears
   misconfigured", and do not write `PREFLIGHT.md`. Do not recompute the
   path and retry -- these are caller misconfigurations (in particular
   `WRITE_SCOPE_OUTSIDE`, meaning `output_dir` itself resolves outside
   `repo_root`) that a fresh guess cannot fix.

2. `<output_dir>/preflight_summary.json` -- the exact JSON object from Step 2,
   unmodified (do not paraphrase or drop fields; the schema is load-bearing
   for `andon-status` and any external tooling that reads it later). Gate
   this write the same way as item 1 -- confirm the path first:

   ```
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/andon_core.py validate-write-path \
     <output_dir>/preflight_summary.json <repo_root> <output_dir>
   ```

   and apply the same handling on failure: stop, report the `AndonError`
   message verbatim as "output_dir appears misconfigured", and do not
   write `preflight_summary.json`.

## Verdict semantics (already computed by the script -- report, don't re-derive)

- `andon-propose`: `Ready` if house-rules found, else `Ready-with-gaps`.
- `andon-verify`: `Ready-with-gaps` at minimum whenever a strategy
  prerequisite is missing, naming exactly which strategies degrade.
- `andon-loop`: `Not-ready` if the ledger directory isn't writable,
  `Ready-with-gaps` if topology detection would be heuristic/reduced, `Ready`
  otherwise.

Report all three plainly even if one is `Not-ready` -- deliver one complete
readiness report, not a halt at the first failing check.
