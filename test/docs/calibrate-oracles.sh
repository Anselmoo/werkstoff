#!/usr/bin/env bash
# Calibrate the journeys.tsv oracles against FABRICATED transcripts, before
# spending a single real token on test/docs/run-journeys.sh.
#
# Per CLAUDE.md: "Never retune an oracle after the thing it grades exists" and
# "oracles are calibrated against fabricated transcripts before first use."
# This script is that calibration, checked in so it can be re-run any time a
# regex in journeys.tsv changes: every row in calibration.tsv copies a regex
# (and antiregex, where used) verbatim from journeys.tsv and asserts it scores
# a hand-written PASS transcript as PASS and a hand-written FAIL transcript as
# FAIL, for each of the three oracle mechanisms the suite uses:
#   - simple:      one literal regex, no @@AND@@, no antiregex
#   - conjunctive: @@AND@@ (used by the two negative "no werkstoff fit" cases
#                  -- see calibration.tsv for why BOTH a FAIL-by-overclaiming
#                  and a FAIL-by-ungrounded-guess fixture exist for this style)
#   - antiregex:   a must-NOT-match column (the confusable red/green CI pair)
#
# This spends zero tokens and calls no LLM. It only proves the MATCHING LOGIC
# behaves as intended -- it says nothing about whether a real `claude --print`
# run would produce the fixture text. That is what run-journeys.sh measures.
#
# Usage: test/docs/calibrate-oracles.sh
# Exit: 0 if every row's actual verdict matches its expected verdict, 1 otherwise.

set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib-oracle-match.sh
source "$HERE/lib-oracle-match.sh"

MANIFEST="$HERE/calibration/calibration.tsv"
FIXTURES="$HERE/calibration/fixtures"
[[ -f "$MANIFEST" ]] || { echo "ERROR: no calibration manifest at $MANIFEST" >&2; exit 2; }

total=0
mismatches=0

echo "calibrating journeys.tsv oracles against fabricated transcripts"
echo

while IFS=$'\t' read -r id style fixture regex expect antiregex; do
  [[ -z "${id:-}" || "$id" == \#* ]] && continue
  total=$((total + 1))
  fpath="$FIXTURES/$fixture"
  if [[ ! -f "$fpath" ]]; then
    echo "  MISCALIBRATED  $id ($style) -- fixture missing: $fixture"
    mismatches=$((mismatches + 1))
    continue
  fi

  verdict_line="$(oracle_verdict "$fpath" "$regex" "$antiregex")"
  actual="PASS"
  [[ "$verdict_line" == FAIL* ]] && actual="FAIL"

  if [[ "$actual" == "$expect" ]]; then
    echo "  ok             $id ($style) -- expected $expect, got $actual"
  else
    echo "  MISCALIBRATED  $id ($style) -- expected $expect, got $actual ($verdict_line)"
    mismatches=$((mismatches + 1))
  fi
done < "$MANIFEST"

echo
if [[ "$mismatches" -eq 0 ]]; then
  echo "calibration passed -- $total/$total fixtures scored as expected"
  echo "the matching logic behaves as intended; the real suite has never run yet, so"
  echo "nothing here has been retuned to fit an observed result (see README.md)"
  exit 0
else
  echo "calibration FAILED -- $mismatches/$total fixtures scored unexpectedly"
  echo "do NOT run run-journeys.sh against a miscalibrated oracle; fix the regex or"
  echo "the fixture (whichever is wrong) and re-run this script until it is clean"
  exit 1
fi
