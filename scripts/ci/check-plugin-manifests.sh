#!/usr/bin/env bash
set -uo pipefail

fail=0

echo "== marketplace.json =="
if ! claude plugin validate --strict .claude-plugin/marketplace.json; then
  fail=1
fi

for dir in plugins/*/; do
  plugin="${dir%/}"
  echo "== $plugin =="
  if ! claude plugin validate --strict "$dir"; then
    fail=1
  fi
done

if [ "$fail" -eq 0 ]; then
  echo "All plugin and marketplace manifests valid."
fi
exit "$fail"
