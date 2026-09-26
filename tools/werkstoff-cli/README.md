# werkstoff

A thin CLI that installs and refreshes this repo's own Claude Code
plugins by driving the `claude` CLI as a subprocess, and never ships a
duplicated copy of `.claude-plugin/marketplace.json` — the manifest is
read live from this repo on every invocation, so there is nothing to keep
in sync. `doctor` and `prune` are the exception: they read (and, with
`prune --apply`, remove from) the plugin cache directly, since that is
exactly the thing they report on.

Requires the `claude` CLI on `PATH` for `list`/`install`/`update`.
`doctor` and `prune` need only this repo's marketplace manifest (to know
the marketplace name and which plugins it declares) and a readable
`installed_plugins.json` registry — no `claude` CLI call.

## Install

```bash
uv tool install .
# or
pipx install .
```

## Usage

```bash
werkstoff list                       # show every plugin in the marketplace
werkstoff list --json                # machine-readable

werkstoff install                    # add the marketplace + install every plugin
werkstoff install befund zeugnis  # install just these two
werkstoff install --no-input         # skip the "install all?" confirmation (CI-safe)
werkstoff install --scope project    # user | project | local

werkstoff update                     # refresh the marketplace cache after editing a plugin locally

werkstoff doctor                     # read-only: report every cached version vs. what's installed
werkstoff doctor --json              # machine-readable

werkstoff prune                      # dry run: list stale, non-live cached versions (keeps newest 1)
werkstoff prune --keep 2             # keep the 2 newest non-live versions per plugin
werkstoff prune --apply              # actually remove them
werkstoff prune --apply --json       # machine-readable
```

`doctor` and `prune` look under
`<claude-dir>/plugins/cache/<marketplace>/<plugin>/<version>/`, where
`<claude-dir>` is `--claude-dir`, else `$CLAUDE_CONFIG_DIR`, else
`~/.claude`, and `<marketplace>` is this repo's own marketplace name. A
version counts as "live" when the registry
(`<claude-dir>/plugins/installed_plugins.json`) names it — by install
path, not by version string — under any scope. `prune` never removes a
live version, an uninstalled plugin's cache, or anything reached through
a symlink, and is a dry run unless `--apply` is given.

By default, `werkstoff` searches upward from the current directory for a
`.claude-plugin/marketplace.json`. Override with `--repo <path>` or the
`WERKSTOFF_REPO` environment variable if you're invoking it from outside
this repo.

## Exit codes

- `0` — success
- `1` — general/runtime error (missing repo, `claude` subprocess failure, declined confirmation)
- `2` — usage error (unknown plugin name, invalid `--scope`, bad flags)

## Development

```bash
uv sync --all-groups
uv run pytest
uv run pytest --snapshot-update   # after intentionally changing --help output
uv run ruff check .
uv run ruff format .
```

## Publishing

```bash
uv build
uv publish
# or
uv build
twine upload dist/*
```
