# Parallel-Safe Research Protocol

This doc is synced verbatim into every plugin's `references/` directory (see
`.rrt.toml`'s `artifact_targets` + `command` entries, source
`tools/symbol-indexer/parallel-safe-research-protocol.md`, regenerated via
`rrt artifacts --regenerate`). It is deliberately generic — no plugin name
is hardcoded — so the copy is byte-identical across plugins and can sit in
a stable, cacheable prompt prefix. Substitute `<plugin-name>` with the
plugin actually running (the agent invoking this protocol knows its own
plugin).

## Purpose

Before broad repository discovery, prefer the published immutable snapshot
over raw `grep`/`cat`. The snapshot is built once, reused by every subsequent
query, and orders of magnitude cheaper per lookup than re-scanning files.

## Resolve the snapshot

Read `analysis/<plugin-name>/current.json` and resolve only the matching
immutable `runs/<generation_id>/` snapshot it points to.

## Query, don't grep

Query `symbol_index.json` for declarations, `file_catalog.json` to narrow the
candidate set, `search.sqlite` (via `--query`) for arbitrary text, and
`artifact_manifest.json`/`evidence_index.json` before repeating a report or
verification command. Use `Read` only on exact locations returned by those
artifacts.

## Prefer an LSP-backed tool over this snapshot when one is available

This snapshot is a regex-based, zero-dependency fallback — deliberately so,
since a plugin asset can't assume any language server is installed. If a
proper language-server-backed tool is available in the session (for
example, Serena's `find_symbol`, `find_referencing_symbols`, or
`get_symbols_overview` MCP tools), prefer it for symbol-level lookups: it
resolves true semantic references (not regex pattern matches) and is more
precise per token. Fall back to this snapshot when no such tool is present,
or for the file-catalog/full-text-search needs an LSP tool doesn't cover.

## Build-or-reuse invocation

If `current.json` is missing, or its `source_fingerprint` no longer matches
the repository, build (or safely wait for a concurrent build to finish, via
the script's own single-flight lock):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/build_symbol_index.py" --repo-path . --plugin-name <plugin-name>
```

Skip the build if `current.json`'s `source_fingerprint` already matches — the
snapshot is still valid.

## Scale guidance

For a repository well under roughly 50 tracked files, the index-build's own
overhead may exceed what a direct `Grep` would cost. This is judgment
guidance for the calling skill or agent to weigh, not an enforced gate — the
indexer itself makes no such size check.

## Fallback triggers

Use `Grep`/`Glob` only when FTS is unavailable, the assignment requires a
regex or inline-content check, a file was generated after the snapshot, or
the audit explicitly requires an exhaustive sweep.

## Guardrails

Never write, promote, or overwrite a shared analysis artifact from an agent
— return structured results to the run coordinator instead. If assigned
source edits, work in the assigned Git worktree only; do not edit the shared
working tree.
