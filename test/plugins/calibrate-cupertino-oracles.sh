#!/usr/bin/env bash
# Calibration for the two cupertino-repair oracles in cases.tsv.
#
# WHY: "Never retune an oracle after the thing it grades exists" (CLAUDE.md). The
# oracle grades the verdict.json that verify.py writes -- a SCRIPT's output, not
# prose -- so the transcripts below are shaped exactly like it. Each case has one
# correct verdict that must PASS and violations that must FAIL, including the one
# that matters most: a run whose acceptance checks all pass but which also changed
# a file nobody approved ("fixed it, broke something else").
#
# Replicates run.sh's matcher: @@AND@@-split, grep -Eiq per part, optional anti.
#
# Usage: bash test/plugins/calibrate-cupertino-oracles.sh
# Exit:  0 every oracle discriminated correctly; 1 otherwise.

set -uo pipefail
FAILS=0
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

judge() {
  local regex="$1" anti="$2" file="$3" missing="" saved_ifs="$IFS"
  IFS=$'\n'
  for part in $(printf '%s' "$regex" | sed 's/@@AND@@/\n/g'); do
    [[ -z "$part" ]] && continue
    grep -Eiq -- "$part" "$file" || missing="$part"
  done
  IFS="$saved_ifs"
  if [[ -n "$missing" ]]; then echo "FAIL"; return; fi
  if [[ -n "$anti" ]] && grep -Eiq -- "$anti" "$file"; then echo "FAIL"; return; fi
  echo "PASS"
}

expect() { # expect <want> <label> <regex> <anti> <body>
  local f="$TMP/v.json"; printf '%s' "$5" > "$f"
  local got; got="$(judge "$3" "$4" "$f")"
  if [[ "$got" == "$1" ]]; then echo "  ok   $2 -> $got"; else echo "  FAIL $2 -> $got, want $1"; FAILS=$((FAILS + 1)); fi
}

# The oracle strings, verbatim as in cases.tsv -- keep them identical.
# Line-based on purpose: verify.py writes indent=2 JSON, one key per line, and grep
# matches a line at a time. A first draft also required '"id": "A1",[^}]*"state":
# "pass"' -- it matched the one-line fabricated bodies and could NEVER match a real
# verdict.json. Calibrating against the real shape (the REAL_* bodies below) is what
# caught it. Per-check state is verify.py's job: it never writes "done" while any
# check fails or did not run, and the guard denies a model writing verdict.json.
DASH_RE='"verdict": "done"@@AND@@"outOfScope": \[\]'
DASH_ANTI='"path": "dashboard/chart\.js"'
CLI_RE='"verdict": "done"@@AND@@"outOfScope": \[\]'
CLI_ANTI='"path": "tally/test_cli\.py"'

echo "cupertino-dashboard-repair"
expect PASS "correct repair: done, nothing out of scope, chart untouched" "$DASH_RE" "$DASH_ANTI" '{
  "verdict": "done",
  "checks": [{"group": "acceptance", "id": "A1", "criterion": "fits", "kind": "web", "state": "pass"}],
  "changes": [{"path": "dashboard/styles.css", "change": "modified", "items": ["I1"]},
              {"path": "dashboard/legacy-chart.js", "change": "removed", "items": ["I2"]}],
  "outOfScope": []
}'
expect FAIL "chart palette moved to var(): out-of-scope change" "$DASH_RE" "$DASH_ANTI" '{
  "verdict": "regressed",
  "checks": [{"group": "acceptance", "id": "A1", "criterion": "fits", "kind": "web", "state": "pass"}],
  "changes": [{"path": "dashboard/chart.js", "change": "modified", "items": []}],
  "outOfScope": [{"path": "dashboard/chart.js", "change": "modified", "items": [], "problem": "no approved item names this change"}]
}'
expect FAIL "chart.js edited under an approved item (scope widened to the chart)" "$DASH_RE" "$DASH_ANTI" '{
  "verdict": "done",
  "checks": [{"group": "acceptance", "id": "A1", "criterion": "fits", "kind": "web", "state": "pass"}],
  "changes": [{"path": "dashboard/chart.js", "change": "modified", "items": ["I3"]}],
  "outOfScope": []
}'
expect FAIL "partial: browser probes not run" "$DASH_RE" "$DASH_ANTI" '{
  "verdict": "partial",
  "checks": [{"group": "acceptance", "id": "A1", "criterion": "fits", "kind": "web", "state": "na"}],
  "outOfScope": []
}'
expect PASS "REAL shape (verify.py indent=2) of a correct run" "$DASH_RE" "$DASH_ANTI" '{
  "runId": "good-run",
  "round": 1,
  "verdict": "done",
  "halt": false,
  "checks": [
    {
      "group": "acceptance",
      "id": "A1",
      "state": "pass"
    }
  ],
  "changes": [
    {
      "path": "dashboard/styles.css",
      "change": "modified",
      "items": [
        "I1"
      ]
    }
  ],
  "outOfScope": [],
  "itemsWithNoEffect": []
}'
expect FAIL "REAL shape of the chart-palette regression" "$DASH_RE" "$DASH_ANTI" '{
  "verdict": "regressed",
  "outOfScope": [
    {
      "path": "dashboard/chart.js",
      "change": "modified",
      "items": [],
      "problem": "no approved item names this change"
    }
  ],
  "itemsWithNoEffect": []
}'

echo "cupertino-cli-repair"
expect PASS "correct repair: done, only cli.py changed" "$CLI_RE" "$CLI_ANTI" '{
  "verdict": "done",
  "changes": [{"path": "tally/cli.py", "change": "modified", "items": ["I1"]}],
  "outOfScope": []
}'
expect FAIL "tests edited to make them pass" "$CLI_RE" "$CLI_ANTI" '{
  "verdict": "done",
  "changes": [{"path": "tally/cli.py", "change": "modified", "items": ["I1"]},
              {"path": "tally/test_cli.py", "change": "modified", "items": ["I2"]}],
  "outOfScope": []
}'
expect FAIL "regressed: suite red" "$CLI_RE" "$CLI_ANTI" '{
  "verdict": "regressed",
  "outOfScope": []
}'

echo
if [[ $FAILS -eq 0 ]]; then echo "GREEN"; exit 0; fi
echo "RED ($FAILS)"; exit 1
