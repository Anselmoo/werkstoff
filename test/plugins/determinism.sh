#!/usr/bin/env bash
# Run each behavior case N times and report a PASS RATE.
#
# Why this exists: run.sh gives a single-shot verdict, which cannot answer the
# question that actually matters for a prose-enforced guard. A rule the model
# honors 5/5 and one it honors 3/5 both show up as "PASS" in a single run, but
# only the first is a guard. Code-enforced rules are 5/5 by construction; the
# gap between them is the whole argument for moving a rule into code.
#
# Usage:
#   test/plugins/determinism.sh                 # every case, N=5
#   test/plugins/determinism.sh thrash-escalate # one case
#   N=10 test/plugins/determinism.sh            # more runs
#
# Env: N (default 5), plus everything run.sh honors (CLAUDE_BIN,
# CLAUDE_PERM_FLAGS, VERBOSE, KEEP_TMP).
#
# Cost warning: each run spawns a fresh `claude` process that fans out
# subagents. At roughly 3-4 min per run, N=5 over 4 cases is about an hour of
# wall clock and real tokens. Start with one case before running the sweep.

set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
N="${N:-5}"
CASES="$HERE/cases.tsv"

[[ -f "$CASES" ]] || { echo "ERROR: no cases file at $CASES" >&2; exit 2; }

if [[ $# -gt 0 ]]; then
  ids=("$@")
else
  mapfile -t ids < <(awk -F'\t' '!/^#/ && NF {print $1}' "$CASES")
fi

echo "determinism sweep — N=$N per case, $(date -u +%FT%TZ)"
echo "a guard worth the name is N/N; anything less is a tendency, not a rule"
echo "======================================================================"

declare -a summary
for id in "${ids[@]}"; do
  pass=0
  printf "%-26s " "$id" >&2
  for _ in $(seq 1 "$N"); do
    if bash "$HERE/run.sh" "$id" 2>/dev/null | grep -q "PASS —"; then
      pass=$((pass + 1)); printf "." >&2
    else
      printf "x" >&2
    fi
  done
  printf "  %d/%d\n" "$pass" "$N" >&2
  summary+=("$(printf '%-26s %d/%d' "$id" "$pass" "$N")")
done

echo ""
echo "==================== PASS RATES ===================="
printf '%s\n' "${summary[@]}"
echo ""
echo "Reading it: N/N = the behavior is reliable under this implementation."
echo "Anything below N/N on a rule the contract states as MUST is the"
echo "empirical case for moving that rule out of prose and into code."
