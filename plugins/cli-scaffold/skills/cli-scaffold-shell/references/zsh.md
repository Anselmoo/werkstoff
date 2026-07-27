# Zsh CLI reference

Sections map 1:1 onto the five pillars in `cli-architecture`.

## Framework
`zparseopts` (or `getopts`) in the entry point. The sourced library holds only
function definitions.

## Project layout (Pillar 2: core separation)
```
<app>/
  bin/<app>            # thin entry: zparseopts -> source lib -> dispatch -> exit
  lib/<app>.zsh        # sourced library: ONLY function defs, zero side effects
  test/help.bats
  test/help.golden
  completions/_<app>   # #compdef completion function
  cli-scaffold.manifest.json
```
`core_files: ["lib/<app>.zsh"]`, `entry_file: "bin/<app>"`.

## Help & completions (Pillar 1)
Hand-written `usage()` (Usage first, then Arguments, then Options). Ship a
first-party zsh completion function `completions/_<app>` beginning with `#compdef`.

## NO_COLOR (Pillar 3)
`[[ -n ${NO_COLOR:-} ]]` disables ANSI (zsh scaffolds may use `[[ ]]`).

## Exit codes (Pillar 3)
`exit <code>` mapped to the frozen contract; parse errors exit the usage code.

## --json / --no-input (Pillar 5)
`--json` emits JSON (via `jq` if available, else built by hand). `--no-input`
(`-n`) disables prompts; missing required input then exits the usage code. Guard
with `[[ -t 0 ]]` to fail fast when stdin is not a TTY.

## stdout / stderr (Pillar 5)
Results via `print`/`printf` to stdout; diagnostics via `print -u2` / `>&2`.

## Distribution (Pillar 4)
**Homebrew**: a formula installing `bin/<app>` and the `_<app>` completion into
the zsh site-functions path.

## Snapshot testing (Pillar 3)
`bats-core` (or `zunit`): capture `--help` and compare to `test/help.golden`.

## Worked example (sketch)
```zsh
# lib/<app>.zsh — sourced, NO side effects (only defs)
greet() {
  local name="$1"
  if [[ -z "$name" ]]; then print -u2 "name required"; return 1; fi
  print -- "Hello, $name"
}
```
```zsh
#!/usr/bin/env zsh
# bin/<app> — thin entry
emulate -L zsh
source "${0:A:h}/../lib/<app>.zsh"
usage() { print -- "Usage: <app> [--json] [-n] [name]"; }
local -a o_json o_noinput o_help
zparseopts -D -E -- -json=o_json n=o_noinput -no-input=o_noinput h=o_help -help=o_help || { usage >&2; exit 2; }
(( $#o_help )) && { usage; exit 0; }
[[ -n ${NO_COLOR:-} ]] && : # no ANSI
local name="${1:-}"
if [[ -z "$name" ]] && { (( $#o_noinput )) || [[ ! -t 0 ]]; }; then print -u2 "error: name required"; exit 2; fi
if out="$(greet "$name")"; then
  if (( $#o_json )); then printf '{"message":"%s"}\n' "$out"; else print -- "$out"; fi
  exit 0
else exit 1; fi
```
