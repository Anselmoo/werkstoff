# POSIX sh CLI reference

Sections map 1:1 onto the five pillars in `cli-architecture`.

## Framework
POSIX `getopts` (short options only) in the entry point, plus a manual loop for
long options. The sourced library holds only function definitions.

## Project layout (Pillar 2: core separation)
```
<app>/
  <app>                # thin entry: parse -> . lib -> dispatch -> exit
  lib/<app>.sh         # sourced library: ONLY function defs, zero side effects
  Makefile             # distribution: `make install`
  test/help_spec.sh    # shellspec
  test/help.golden
  cli-scaffold.manifest.json
```
`core_files: ["lib/<app>.sh"]`, `entry_file: "<app>"`.

## Forbidden bashisms (Pillar 3 — the verifier sweeps for these)

`verify_scaffold.py` flags any of the following in a POSIX sh scaffold. **Do not
emit them.** This list mirrors `FORBIDDEN_BASHISMS` in `scripts/constants.py`:

| Forbidden | Use instead |
|---|---|
| Arrays — `name=(a b c)` | positional params `set -- a b c` / space-separated string |
| `[[ ... ]]` test keyword | the POSIX `[ ... ]` / `test` |
| `function name {` keyword | `name() { ... }` |
| `==` inside `[ ... ]` | `=` for string equality |
| Here-strings — `<<<` | a here-doc `<<EOF` or a pipe |
| Process substitution — `<( )` / `>( )` | a temp file or a pipe |

Also avoid other non-POSIX constructs (`local` is not in POSIX — use a subshell or
unique variable names; no `$'...'`, no `source` — use `.`).

## Help & completions (Pillar 1)
Hand-written `usage()` (Usage first, then Arguments, then Options). **POSIX sh has
no portable native completion mechanism** — declare it honestly in the manifest:
`"completion": {"supported": false, "note": "POSIX sh has no native completion mechanism"}`.

## NO_COLOR (Pillar 3)
`[ -n "${NO_COLOR:-}" ]` disables ANSI.

## Exit codes (Pillar 3)
`exit <code>` mapped to the frozen contract; `getopts` `\?`/`:` cases exit the
usage code.

## --json / --no-input (Pillar 5)
`--json` emits JSON built with `printf` (no `jq` dependency assumed).
`--no-input` (`-n`) disables prompts; missing required input then exits the usage
code. Guard with `[ -t 0 ]` to fail fast when stdin is not a TTY.

## stdout / stderr (Pillar 5)
Results via `printf` to stdout; diagnostics via `printf ... >&2`.

## Distribution (Pillar 4)
**`make install`**: a `Makefile` installing the script to `$(PREFIX)/bin` using
`install(1)` — the portable, idiomatic channel for a POSIX sh tool.

## Snapshot testing (Pillar 3)
`shellspec`: capture `--help` and compare to `test/help.golden`.

## Worked example (sketch)
```sh
# lib/<app>.sh — sourced, NO side effects (only defs), pure POSIX
greet() {
  name="$1"
  if [ -z "$name" ]; then printf 'name required\n' >&2; return 1; fi
  printf 'Hello, %s\n' "$name"
}
```
```sh
#!/bin/sh
# <app> — thin entry, pure POSIX
set -eu
. "$(dirname "$0")/lib/<app>.sh"
usage() { printf 'Usage: <app> [-j] [-n] [name]\n'; }
json=0; no_input=0
while getopts jnh opt; do
  case "$opt" in
    j) json=1 ;; n) no_input=1 ;; h) usage; exit 0 ;;
    ?) usage >&2; exit 2 ;;
  esac
done
shift $((OPTIND - 1))
name="${1:-}"
[ -n "${NO_COLOR:-}" ] && : # no ANSI
if [ -z "$name" ] && { [ "$no_input" -eq 1 ] || [ ! -t 0 ]; }; then
  printf 'error: name required\n' >&2; exit 2
fi
if out="$(greet "$name")"; then
  if [ "$json" -eq 1 ]; then printf '{"message":"%s"}\n' "$out"; else printf '%s\n' "$out"; fi
  exit 0
else
  exit 1
fi
```
