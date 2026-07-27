# Bash CLI reference

Sections map 1:1 onto the five pillars in `cli-architecture`.

## Framework
Bash `getopts` (builtin) in the entry point. The sourced library holds only
function definitions.

## Project layout (Pillar 2: core separation)
```
<app>/
  bin/<app>            # thin entry: getopts -> source lib -> dispatch -> exit
  lib/<app>.sh         # sourced library: ONLY function defs, zero side effects
  test/help.bats
  test/help.golden
  completions/<app>.bash
  cli-scaffold.manifest.json
```
`core_files: ["lib/<app>.sh"]`, `entry_file: "bin/<app>"`.

## Help & completions (Pillar 1)
Hand-written `usage()` printing a Usage summary first, then Arguments, then
Options. Ship a `bash-completion` script under `completions/` (near-first-party).

## NO_COLOR (Pillar 3)
`[ -n "${NO_COLOR:-}" ]` disables ANSI.

## Exit codes (Pillar 3)
`exit <code>` mapped to the frozen contract; `getopts` `\?`/`:` cases exit the
usage code.

## --json / --no-input (Pillar 5)
`--json` emits JSON (via `jq` if available, else `printf`-built). `--no-input`
(`-n`) disables prompts; missing required input then exits the usage code. Guard
with `[ -t 0 ]` to fail fast when stdin is not a TTY.

## stdout / stderr (Pillar 5)
Results via `printf`/`echo` to stdout; diagnostics via `printf ... >&2`.

## Distribution (Pillar 4)
**Homebrew**: a formula (tap) installing `bin/<app>` and completions.

## Snapshot testing (Pillar 3)
`bats-core`: capture `--help` and compare to `test/help.golden`.

## Worked example (sketch)
```bash
# lib/<app>.sh — sourced, NO side effects (only defs)
greet() {
  local name="$1"
  if [ -z "$name" ]; then printf 'name required\n' >&2; return 1; fi
  printf 'Hello, %s\n' "$name"
}
```
```bash
#!/usr/bin/env bash
# bin/<app> — thin entry
set -euo pipefail
. "$(dirname "$0")/../lib/<app>.sh"
usage() { printf 'Usage: <app> [-j] [-n] [name]\n'; }
json=0; no_input=0
while getopts ":jnh-:" opt; do
  case "$opt" in
    j) json=1 ;; n) no_input=1 ;; h) usage; exit 0 ;;
    -) case "$OPTARG" in json) json=1 ;; no-input) no_input=1 ;; help) usage; exit 0 ;; *) usage >&2; exit 2 ;; esac ;;
    \?|:) usage >&2; exit 2 ;;
  esac
done
shift $((OPTIND-1))
name="${1:-}"
[ -n "${NO_COLOR:-}" ] && : # no ANSI
if [ -z "$name" ] && { [ "$no_input" -eq 1 ] || [ ! -t 0 ]; }; then printf 'error: name required\n' >&2; exit 2; fi
if out="$(greet "$name")"; then
  if [ "$json" -eq 1 ]; then printf '{"message":"%s"}\n' "$out"; else printf '%s\n' "$out"; fi
  exit 0
else exit 1; fi
```
