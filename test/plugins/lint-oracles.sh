#!/usr/bin/env bash
# Lint cases.tsv for regex constructs that fail SILENTLY.
#
# Three separate oracles in this repo were miscalibrated by metacharacter
# semantics that produce no error — they just never match, so a correct run
# scores FAIL and nobody notices:
#
#   [^\n]   in a POSIX bracket expression means "not backslash, not the letter
#           n". Any text containing an 'n' fails. grep is line-oriented, so the
#           intended meaning is plain `.`.
#   \b!==\b `\b` asserts a word boundary; there is no word character adjacent to
#           '!' or '=', so this can never match.
#   [^.]{0,N}
#           intended as "within one sentence", but file names and module paths
#           contain dots — `report/build.py ... export/dump.py` never spans it.
#
# Run before any sweep. Costs nothing; each of these cost a sweep to find.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CASES="$HERE/cases.tsv"
bad=0

check() { # pattern description
  local hits
  hits="$(awk -F'\t' '!/^#/ && NF {print $1"\t"$6"\t"$7}' "$CASES" | grep -nF -- "$1" || true)"
  if [[ -n "$hits" ]]; then
    echo "  FAIL  $2"
    while IFS= read -r h; do echo "        case: $(cut -f1 <<<"${h#*:}")"; done <<<"$hits"
    bad=$((bad + 1))
  else
    echo "  ok    no $2"
  fi
}

echo "linting oracle regexes in cases.tsv"
check '[^\n]'   '[^\n] (means "not backslash, not n" — use . instead)'
check '\b!=='   '\b around punctuation (never matches)'
check '\b==='   '\b around punctuation (never matches)'

# [^.] is legitimate for short windows but not across a filename. Flag only the
# wide ones, where a dotted path is likely to appear inside the window.
wide="$(awk -F'\t' '!/^#/ && NF {print $1"\t"$6}' "$CASES" | grep -E '\[\^\.\]\{0,([5-9][0-9]|[0-9]{3,})\}' | cut -f1 || true)"
if [[ -n "$wide" ]]; then
  echo "  WARN  [^.]{0,50+} — will not span a file name or module path:"
  echo "$wide" | sed 's/^/        case: /'
else
  echo "  ok    no wide [^.] windows"
fi

echo
[[ "$bad" -eq 0 ]] && echo "oracle lint passed" || echo "oracle lint FAILED — these never match, so they score correct runs as FAIL"
exit "$bad"
