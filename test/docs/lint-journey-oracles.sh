#!/usr/bin/env bash
# Lint journeys.tsv and calibration.tsv for regex constructs that fail SILENTLY.
#
# A sibling of test/plugins/lint-oracles.sh, not a wired invocation of it:
# that script hardcodes CASES="$HERE/cases.tsv" with no override, and this
# task's ownership boundary is test/docs/ only -- test/plugins/lint-oracles.sh
# is owned by a concurrently-running agent, so it is read here (to copy its
# exact check logic) but not edited or pointed at this suite's files. If that
# script ever grows a CASES_FILE override, wire this one to source it instead
# of duplicating the checks.
#
# Same three silent-failure forms as the plugin harness's lint, for the same
# reason -- CLAUDE.md's defect table lists all three as things that have
# already cost a sweep here:
#   [^\n]     in a POSIX bracket expression means "not backslash, not the
#             letter n", not ".". grep is line-oriented; the intended meaning
#             is plain `.`.
#   \b!==\b   `\b` asserts a word boundary; no word character is adjacent to
#             '!' or '=', so this can never match.
#   [^.]{0,N} intended as "within one sentence" but silently fails to span a
#             dotted file name or module path once N gets wide.
#
# Run before any real run-journeys.sh sweep and before calibrate-oracles.sh.
# Costs nothing.

set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
JOURNEYS="$HERE/journeys.tsv"
CALIBRATION="$HERE/calibration/calibration.tsv"
bad=0

# journeys.tsv: regex is column 5, antiregex is column 6 (optional, last).
# calibration.tsv: regex is column 4, antiregex is column 6 (optional, last).
check_file() {
  local file="$1" regex_col="$2" anti_col="$3" label="$4"
  local hits

  hits="$(awk -F'\t' -v rc="$regex_col" -v ac="$anti_col" \
    '!/^#/ && NF {print $1"\t"$(rc)"\t"$(ac)}' "$file" \
    | grep -nF -- '[^\n]' || true)"
  if [[ -n "$hits" ]]; then
    echo "  FAIL  $label: [^\\n] (means \"not backslash, not n\" -- use . instead)"
    while IFS= read -r h; do echo "        case: $(cut -f1 <<<"${h#*:}")"; done <<<"$hits"
    bad=$((bad + 1))
  else
    echo "  ok    $label: no [^\\n]"
  fi

  for pat in '\b!==' '\b==='; do
    hits="$(awk -F'\t' -v rc="$regex_col" -v ac="$anti_col" \
      '!/^#/ && NF {print $1"\t"$(rc)"\t"$(ac)}' "$file" \
      | grep -nF -- "$pat" || true)"
    if [[ -n "$hits" ]]; then
      echo "  FAIL  $label: \\b around punctuation (never matches) -- $pat"
      while IFS= read -r h; do echo "        case: $(cut -f1 <<<"${h#*:}")"; done <<<"$hits"
      bad=$((bad + 1))
    else
      echo "  ok    $label: no \\b-around-punctuation ($pat)"
    fi
  done

  local wide
  wide="$(awk -F'\t' -v rc="$regex_col" '!/^#/ && NF {print $1"\t"$(rc)}' "$file" \
    | grep -E '\[\^\.\]\{0,([5-9][0-9]|[0-9]{3,})\}' | cut -f1 || true)"
  if [[ -n "$wide" ]]; then
    echo "  WARN  $label: [^.]{0,50+} -- will not span a file name or module path:"
    echo "$wide" | sed 's/^/        case: /'
  else
    echo "  ok    $label: no wide [^.] windows"
  fi
}

echo "linting oracle regexes in journeys.tsv and calibration.tsv"
[[ -f "$JOURNEYS" ]] && check_file "$JOURNEYS" 5 6 "journeys.tsv" || { echo "ERROR: missing $JOURNEYS" >&2; bad=$((bad+1)); }
echo
[[ -f "$CALIBRATION" ]] && check_file "$CALIBRATION" 4 6 "calibration.tsv" || { echo "ERROR: missing $CALIBRATION" >&2; bad=$((bad+1)); }

echo
[[ "$bad" -eq 0 ]] && echo "oracle lint passed" || echo "oracle lint FAILED -- these never match, so they score correct runs as FAIL"
exit "$bad"
