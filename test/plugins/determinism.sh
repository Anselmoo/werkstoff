#!/usr/bin/env bash
# Run each behavior case N times and report a PASS RATE.
#
# Why this exists: run.sh gives a single-shot verdict, which cannot answer the
# question that actually matters for a prose-enforced guard. A rule the model
# honors 5/5 and one it honors 3/5 both show up as "PASS" in a single run, but
# only the first is a guard. Code-enforced rules are 5/5 by construction; the
# gap between them is the whole argument for moving a rule into code.
#
# ERROR runs (claude never produced output) are tallied SEPARATELY and never
# counted as passes or failures. A dead process is evidence about the harness,
# not about the plugin — conflating the two is what made the cloud pilot's
# first sweep vacuous. A rate is only trustworthy if its error count is 0.
#
# Usage:
#   test/plugins/determinism.sh                 # every case, N=5
#   test/plugins/determinism.sh thrash-escalate # one case
#   N=10 test/plugins/determinism.sh            # more runs
#   J=3 test/plugins/determinism.sh             # 3 runs concurrently
#
# Env: N (default 5), J (default 1 — concurrent runs), RUN_LOG_DIR (default a
# timestamped dir under analysis/andon-pilot/), plus everything run.sh honors
# (CLAUDE_BIN, CLAUDE_PERM_FLAGS, VERBOSE, KEEP_TMP, CLEAN_BOX).
# SKIP_CLEAN_BOX_VERIFY=1 skips this script's own one-time isolation proof
# (see below); it is then also exported so the N per-iteration run.sh calls
# do not each re-verify it.
#
# Cost warning: each run spawns a fresh `claude` process that fans out
# subagents. At roughly 3-4 min per run, N=5 over 4 cases is about an hour of
# wall clock at J=1 and real tokens. Start with one case before the sweep.

set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(git -C "$HERE" rev-parse --show-toplevel)"
N="${N:-5}"
J="${J:-1}"
CASES="$HERE/cases.tsv"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
RUN_LOG_DIR="${RUN_LOG_DIR:-$REPO_ROOT/analysis/andon-pilot/$STAMP}"
export RUN_LOG_DIR

[[ -f "$CASES" ]] || { echo "ERROR: no cases file at $CASES" >&2; exit 2; }
mkdir -p "$RUN_LOG_DIR"

if [[ $# -gt 0 ]]; then
  ids=("$@")
else
  mapfile -t ids < <(awk -F'\t' '!/^#/ && NF {print $1}' "$CASES")
fi

# Prove clean-box isolation ONCE for the whole sweep, not once per iteration.
# Every iteration below shells out to run.sh, which would otherwise call
# verify-clean-box.sh N times per case — real tokens each time, for a
# question that does not change between iterations of the same case. See
# run.sh's CLEAN BOX comment for why this must not be skipped outright.
# Escape hatch: SKIP_CLEAN_BOX_VERIFY=1, same variable run.sh honors.
if [[ "${CLEAN_BOX:-1}" == "1" && "${SKIP_CLEAN_BOX_VERIFY:-0}" != "1" ]]; then
  plugins_needed=()
  while IFS=$'\t' read -r cid cplugin _rest; do
    [[ -z "${cid:-}" || "$cid" == \#* ]] && continue
    for want in "${ids[@]}"; do
      [[ "$cid" == "$want" ]] && { plugins_needed+=("$cplugin"); break; }
    done
  done < "$CASES"
  mapfile -t _cb_plugins < <(printf '%s\n' "${plugins_needed[@]}" | sort -u)
  if [[ "${#_cb_plugins[@]}" -eq 0 ]]; then
    echo "ERROR: no matching cases to determine which plugin(s) to clean-box-verify." >&2
    exit 2
  fi
  echo "verifying clean-box isolation once for: ${_cb_plugins[*]}" >&2
  if ! bash "$HERE/verify-clean-box.sh" "${_cb_plugins[@]}"; then
    echo "ERROR: clean box is NOT isolated — refusing to run the sweep against a contaminated box." >&2
    echo "       Set SKIP_CLEAN_BOX_VERIFY=1 to bypass, only if isolation was already verified for this plugin set." >&2
    exit 2
  fi
  export SKIP_CLEAN_BOX_VERIFY=1
fi

echo "determinism sweep — N=$N per case, J=$J concurrent, $(date -u +%FT%TZ)"
echo "a guard worth the name is N/N; anything less is a tendency, not a rule"
echo "transcripts: $RUN_LOG_DIR"
echo "======================================================================"

# One run = one (case, iteration). Writes a single verdict token to a file so
# the parent can tally without a shared-state race between concurrent jobs.
one_run() {
  local id="$1" i="$2" out="$RUN_LOG_DIR/verdict.$id.$i"
  local log="$RUN_LOG_DIR/run.$id.$i.log"
  bash "$HERE/run.sh" "$id" >"$log" 2>&1
  # Trust the explicit VERDICT line, not an exit code or a grep for "PASS".
  local v
  v="$(awk -v id="$id" '$1=="VERDICT" && $2==id {print $3}' "$log" | tail -1)"
  printf '%s' "${v:-ERROR}" > "$out"
}

for id in "${ids[@]}"; do
  printf "%-26s " "$id" >&2
  running=0
  for i in $(seq 1 "$N"); do
    one_run "$id" "$i" &
    running=$((running + 1))
    if [[ "$running" -ge "$J" ]]; then wait -n 2>/dev/null || wait; running=$((running - 1)); fi
  done
  wait
  for i in $(seq 1 "$N"); do
    case "$(cat "$RUN_LOG_DIR/verdict.$id.$i" 2>/dev/null)" in
      PASS)  printf "." >&2 ;;
      FAIL)  printf "x" >&2 ;;
      *)     printf "!" >&2 ;;
    esac
  done
  printf "\n" >&2
done

echo ""
echo "==================== PASS RATES ===================="
printf '%-26s %6s %6s %6s\n' case pass fail error
for id in "${ids[@]}"; do
  p=0; f=0; e=0
  for i in $(seq 1 "$N"); do
    case "$(cat "$RUN_LOG_DIR/verdict.$id.$i" 2>/dev/null)" in
      PASS) p=$((p+1)) ;; FAIL) f=$((f+1)) ;; *) e=$((e+1)) ;;
    esac
  done
  printf '%-26s %5d/%d %6d %6d\n' "$id" "$p" "$N" "$f" "$e"
done
echo ""
echo "Reading it: N/N with 0 errors = the behavior is reliable under this"
echo "implementation. Anything below N/N on a rule the contract states as MUST"
echo "is the empirical case for moving that rule out of prose and into code."
echo "Any error count above 0 invalidates that case's rate — read the logs in"
echo "$RUN_LOG_DIR before drawing a conclusion from it."
