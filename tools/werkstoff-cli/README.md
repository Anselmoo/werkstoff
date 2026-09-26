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
`~/.claude`, and `<marketplace>` is this repo's own marketplace name. Both
resolve symlinks first, so a relative `--claude-dir`, or a `~/.claude` that
is itself a symlink, names the same cache.

A version counts as "live" when the registry
(`<claude-dir>/plugins/installed_plugins.json`) names it by install path,
under any scope. `prune` is a dry run unless `--apply` is given, and it:

- **fails closed per plugin** — it prunes a plugin only when every one of
  its registry entries has an absolute `installPath` that exists and lies
  inside that plugin's cache directory, and at least one of them is proven.
  Otherwise (an empty entry list, no `installPath`, a relative or `~` one,
  one that no longer exists or names a file) the plugin's liveness is
  unknown, so it is reported as skipped and nothing of it is touched;
- never removes anything **any** registry entry names, under any key or
  marketplace, compared by device and inode rather than by spelling;
- never removes a version directory that contains something a registry
  entry names, or a mount point — `rmtree` would take either with it;
- never removes an uninstalled plugin's cache, a symlinked plugin or
  version directory, or anything outside
  `<claude-dir>/plugins/cache/<marketplace>/<plugin>/<version>/` after
  symlinks are resolved;
- re-reads the registry and re-checks each path immediately before removing
  it, then removes it through directory handles verified against what was
  checked, so an install that lands mid-prune, or a directory swapped in
  under the same name, is refused rather than deleted.

A missing, unparseable, non-UTF-8, duplicate-keyed or non-regular-file
registry makes both commands exit `1` with a one-line error. `prune --apply
--json` reports what was actually `removed`, what `failed`, and which
plugins were `skipped`, beside the planned `remove` list.

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
