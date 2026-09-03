#!/usr/bin/env bash
# Shared oracle-matching logic for the docs journey-test suite.
#
# This is a straight extraction of the matching logic already proven in
# test/plugins/run.sh (the @@AND@@ conjunctive-regex split, then the optional
# antiregex must-NOT-match check) into a sourceable function. It exists so
# run-journeys.sh (real `claude --print` transcripts) and calibrate-oracles.sh
# (fabricated transcripts) grade with the EXACT SAME code path. Two
# independent re-implementations of "does this regex match" is exactly the
# kind of drift CLAUDE.md's "verify the instrument" section warns about --
# if the calibration script and the real runner disagreed about what a regex
# means, calibrating the former would prove nothing about the latter.
#
# Source this file, then call:
#   oracle_verdict <target_file> <regex> [antiregex]
# It echoes one line ("PASS", or "FAIL missing:/<pattern>/", or
# "FAIL antipattern:/<pattern>/") and returns 0 for PASS, 1 for FAIL.
#
# Regex conventions carried over from test/plugins/cases.tsv (see also
# test/plugins/lint-oracles.sh, which bans the forms below):
#   - `regex` may be several patterns joined by literal `@@AND@@`; ALL must
#     match (grep -Eiq) for the case to pass this half.
#   - `antiregex` is optional; if given and it matches, the case FAILS even
#     if `regex` matched -- a must-NOT-match assertion.
#   - Never write [^.]{0,N} across what might be a dotted path/filename,
#     [^\n] inside a bracket expression, or \b next to non-word punctuation --
#     all three fail silently (match nothing, ever) rather than erroring.

oracle_verdict() {
  local target="$1" regex="$2" antiregex="${3:-}"
  local missing="" part
  local saved_ifs="$IFS"
  IFS=$'\n'
  for part in $(printf '%s' "$regex" | sed 's/@@AND@@/\n/g'); do
    [[ -z "$part" ]] && continue
    grep -Eiq -- "$part" "$target" || missing="$part"
  done
  IFS="$saved_ifs"

  if [[ -n "$missing" ]]; then
    echo "FAIL missing:/$missing/"
    return 1
  fi
  if [[ -n "$antiregex" ]] && grep -Eiq -- "$antiregex" "$target"; then
    echo "FAIL antipattern:/$antiregex/"
    return 1
  fi
  echo "PASS"
  return 0
}
