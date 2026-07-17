# werkstoff

A thin CLI that installs and refreshes this repo's own Claude Code
plugins by driving the `claude` CLI as a subprocess — it never talks to
the plugin cache directly, and it never ships a duplicated copy of
`.claude-plugin/marketplace.json`. The manifest is read live from this
repo on every invocation, so there is nothing to keep in sync.

Requires the `claude` CLI on `PATH`.

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
werkstoff install self-assess quality  # install just these two
werkstoff install --no-input         # skip the "install all?" confirmation (CI-safe)
werkstoff install --scope project    # user | project | local

werkstoff update                     # refresh the marketplace cache after editing a plugin locally
```

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
