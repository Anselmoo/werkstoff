#!/usr/bin/env bash
set -euo pipefail

fail=0
count=0
while IFS= read -r -d '' file; do
  count=$((count + 1))
  if ! node --check "$file" 2>&1; then
    echo "FAIL: $file"
    fail=1
  fi
done < <(find plugins -path '*/workflows/*.js' -print0 | sort -z)

if [ "$fail" -eq 0 ]; then
  echo "All $count workflow .js file(s) parse cleanly."
fi
exit "$fail"
