#!/usr/bin/env bash
# Executes a cupertino-prototype spike and proves it actually ran.
#
# prototype-must-run: the spike MUST be minimal, real, and actually
# runnable/executable -- never a mockup, wireframe, or purely descriptive
# artifact. A skill that only *describes* what a prototype would do has not
# satisfied this guarantee. This script is the mechanical proof: it refuses
# to report success unless a process actually executed and exited.
#
# Usage: run_prototype.sh <file> [args...]
set -euo pipefail

if [ "$#" -lt 1 ]; then
  echo '{"ok": false, "error": "no prototype file given"}' >&2
  exit 2
fi

file="$1"
shift

if [ ! -f "$file" ]; then
  echo "{\"ok\": false, \"error\": \"prototype file does not exist: $file\"}" >&2
  exit 2
fi

case "$file" in
  *.py) cmd=(python3 "$file" "$@") ;;
  *.js|*.mjs) cmd=(node "$file" "$@") ;;
  *.ts) cmd=(npx --yes tsx "$file" "$@") ;;
  *.sh) cmd=(bash "$file" "$@") ;;
  *.rb) cmd=(ruby "$file" "$@") ;;
  *.go) cmd=(go run "$file" "$@") ;;
  *)
    echo "{\"ok\": false, \"error\": \"no runner registered for extension of $file -- prototype-must-run cannot be satisfied for this file type without a runnable entry point\"}" >&2
    exit 2
    ;;
esac

start_marker="--- cupertino prototype run: $(basename "$file") ---"
echo "$start_marker"
set +e
output="$("${cmd[@]}" 2>&1)"
status=$?
set -e
echo "$output"
echo "--- exit code: $status ---"

if [ $status -ne 0 ]; then
  echo "{\"ok\": false, \"error\": \"prototype exited non-zero ($status) -- fix the spike or report the failure as the empirical observation, do not claim it ran cleanly\"}" >&2
  exit 1
fi

echo '{"ok": true}'
