#!/usr/bin/env bash
# Prove the clean box actually isolates, before a sweep spends tokens on it.
#
# The pilot lost ~35 runs to contamination that looked exactly like data: Arm C
# scored a PASS by quoting a rule from the installed legacy plugin. A tally
# cannot show you that. So assert isolation directly and cheaply: ask a run
# which skills it can see, and require the answer to contain ONLY the arm under
# test.
#
# Usage: test/plugins/verify-clean-box.sh [plugin-dir ...]
#        (defaults to both pilot arms)
# Exit: 0 isolated, 1 leakage detected, 2 harness problem.

set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(git -C "$HERE" rev-parse --show-toplevel)"
CLAUDE_BIN="${CLAUDE_BIN:-claude}"

arms=("$@")
[[ ${#arms[@]} -eq 0 ]] && arms=("plugins/andon" "pilot-armc/andon-official")

box="$(mktemp -t cleanbox).json"
python3 "$HERE/make-clean-box.py" "$box" || exit 2

Q="List the exact names of every skill and agent available to you. Output ONLY a comma-separated list of names."
rc=0
for arm in "${arms[@]}"; do
  # The expected namespace is the plugin's own manifest name.
  ns="$(python3 -c "import json,sys;print(json.load(open('$REPO_ROOT/$arm/.claude-plugin/plugin.json'))['name'])" 2>/dev/null)"
  [[ -z "$ns" ]] && { echo "  ERROR $arm: no plugin.json name"; rc=2; continue; }

  tmp="$(mktemp -d)"
  out="$( cd "$tmp" && timeout 240 "$CLAUDE_BIN" --plugin-dir "$REPO_ROOT/$arm" \
            --settings "$box" --print "$Q" --permission-mode bypassPermissions 2>&1 )"
  rm -rf "$tmp"

  if [[ -z "$out" ]] || grep -Eiq "hit your (session|usage) limit|not logged in" <<<"$out"; then
    echo "  ERROR $arm: run did not complete — $(head -c 80 <<<"$out")"
    rc=2; continue
  fi

  # Leakage = any namespaced skill whose namespace is not this arm's. Personal
  # (unnamespaced) skills are checked separately below.
  foreign="$(grep -oE '[a-z0-9-]+:[a-z0-9-]+' <<<"$out" | grep -v "^$ns:" | sort -u | tr '\n' ' ')"
  # The two personal skills that shadow the plugin under test by bare name.
  personal="$(grep -oE '(^|[ ,])(andon-loop|build-andon-plugin)([ ,]|$)' <<<"$out" | tr -d ' ,' | sort -u | tr '\n' ' ')"

  if [[ -n "$foreign" || -n "$personal" ]]; then
    echo "  LEAK  $arm — foreign: ${foreign:-none} | personal: ${personal:-none}"
    rc=1
  else
    echo "  ok    $arm — only $ns:* visible"
  fi
done

echo
[[ "$rc" -eq 0 ]] && echo "clean box verified" || echo "NOT isolated — do not trust any sweep run in this state"
exit "$rc"
