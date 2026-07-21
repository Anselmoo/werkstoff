#!/usr/bin/env bash
# Scaffold a new headless plugin behavior-test case: a seeded-defect fixture +
# a row in cases.tsv. This is the mechanical half of the /scaffold-plugin-test
# command — run it directly, or let that command drive it.
#
# Usage:
#   test/plugins/scaffold-test.sh <id> <plugin-name> <fixture-name> [artifact]
# Example:
#   test/plugins/scaffold-test.sh docs-drift self-assess stale-readme analysis/self-assess/DOCS_DRIFT.md
#
# It creates plugins/<plugin-name>/test-fixtures/<fixture-name>/ with a README
# describing the seeded defect + expected finding (you fill in the actual
# defect file), and appends a TODO case to cases.tsv for you to complete
# (prompt + regex). Nothing is overwritten — it refuses if either exists.

set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(git -C "$HERE" rev-parse --show-toplevel)"
CASES="$HERE/cases.tsv"

id="${1:-}"; plugin="${2:-}"; fixture="${3:-}"; artifact="${4:-analysis/${2:-PLUGIN}/CHANGE_ME.md}"
if [[ -z "$id" || -z "$plugin" || -z "$fixture" ]]; then
  echo "usage: $0 <id> <plugin-name> <fixture-name> [artifact]" >&2; exit 2
fi
[[ -d "$REPO_ROOT/plugins/$plugin" ]] || { echo "ERROR: no plugin dir plugins/$plugin" >&2; exit 2; }

fixdir="$REPO_ROOT/plugins/$plugin/test-fixtures/$fixture"
[[ -e "$fixdir" ]] && { echo "ERROR: fixture already exists: $fixdir" >&2; exit 2; }
grep -Eq "^${id}\b" "$CASES" 2>/dev/null && { echo "ERROR: case id '$id' already in cases.tsv" >&2; exit 2; }

mkdir -p "$fixdir"
cat >"$fixdir/README.md" <<EOF
# $fixture fixture

Seeded-defect fixture for the \`$id\` behavior test (see \`test/plugins/cases.tsv\`).

- **Seeded defect:** <describe the ONE known problem this fixture carries>
- **Expected finding:** <what the plugin must surface — the harness asserts on it>
- **Guardrail (must NOT be flagged):** <optional: a correct case that would be a
  false positive if flagged>

Add the actual defect file(s) next to this README, then fill in the \`prompt\`
and \`regex\` columns of the \`$id\` row in \`test/plugins/cases.tsv\`.
EOF

# Append a TODO case (tab-separated). Prompt/regex are placeholders to complete.
printf '%s\t%s\t%s\t%s\t%s\t%s\n' \
  "$id" \
  "plugins/$plugin" \
  "plugins/$plugin/test-fixtures/$fixture" \
  "TODO-prompt-that-triggers-the-skill-for-$id" \
  "$artifact" \
  "TODO-regex-proving-the-seeded-defect-was-caught" \
  >>"$CASES"

echo "Scaffolded:"
echo "  fixture  $fixdir/  (add the defect file + finish the README)"
echo "  case     appended '$id' to test/plugins/cases.tsv (fill in prompt + regex)"
echo "Then run:  test/plugins/run.sh $id"
