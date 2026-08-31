#!/usr/bin/env bash
# Headless behavior tests for werkstoff's plugins.
#
# WHY headless: Claude Code builds its skill/agent registry once, at session
# start. A skill or agent you just authored is invisible until a reload, so it
# cannot be exercised in the same session that wrote it. Each `claude --print`
# below is a FRESH process = a fresh registry — the only reliable way to test a
# new/edited skill or agent. (Workflows are the exception: the Workflow tool
# reads the .js from disk, but anything routing to a NEW agentType still needs
# a fresh process.) See CLAUDE.md "Verifying plugin changes".
#
# Each case copies a seeded-defect fixture into a temp cwd, runs one plugin
# against it via `--plugin-dir`, and asserts the produced artifact contains the
# finding the plugin is supposed to catch (a golden oracle, not a fuzzy match).
#
# Usage:
#   test/plugins/run.sh              # run every case
#   test/plugins/run.sh ui-audit     # run one case by id
# Env:
#   CLAUDE_BIN        (default: claude)          the CLI to invoke
#   CLAUDE_PERM_FLAGS (default: --permission-mode bypassPermissions, or
#                      --permission-mode acceptEdits when running as root,
#                      where the CLI rejects bypassPermissions outright)
#   VERBOSE=1         print the first 40 lines of a failed target
#   KEEP_TMP=1        keep temp dirs for debugging instead of removing them
#   RUN_LOG_DIR=dir   preserve every run's stdout/stderr there (for sweeps)
#   MIN_STDOUT_BYTES  (default 200) below this, a run is ERROR not FAIL
#   CLEAN_BOX=0             skip the clean-box settings entirely (reproduces
#                           pre-isolation behavior; see the CLEAN BOX comment)
#   SKIP_CLEAN_BOX_VERIFY=1 escape hatch: skip proving isolation via
#                           verify-clean-box.sh before running cases. Only for
#                           callers (e.g. determinism.sh) that already proved
#                           isolation for this exact plugin set this session.
#
# Verdicts are PASS / FAIL / ERROR. ERROR means the run never really happened —
# no output, a CLI refusal banner (session/usage limit, bad key, not logged
# in), or a reply too short to be a skill report. That says nothing about the
# plugin and must not be scored either way; a case whose error count is above
# zero has no rate, only missing data. Each case emits a machine-parseable
# "VERDICT <id> <PASS|FAIL|ERROR>" line for determinism.sh to tally.
#
# Exit: 0 iff at least one case ran and none failed or errored; 2 if the CLI
# is missing.

set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(git -C "$HERE" rev-parse --show-toplevel)"
CASES="$HERE/cases.tsv"
CLAUDE_BIN="${CLAUDE_BIN:-claude}"
# bypassPermissions maps to --dangerously-skip-permissions, which the CLI
# refuses outright under root/sudo — so the old unconditional default made
# every case die with an empty stdout and rc=1, which reads as a plugin
# failure rather than a harness failure. Fall back to acceptEdits when root;
# each case already runs in a throwaway temp cwd, so the sandboxing that
# bypassPermissions trades away is not what is containing the run.
if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
  CLAUDE_PERM_FLAGS="${CLAUDE_PERM_FLAGS:---permission-mode acceptEdits}"
else
  CLAUDE_PERM_FLAGS="${CLAUDE_PERM_FLAGS:---permission-mode bypassPermissions}"
fi
FILTER="${1:-}"

if ! command -v "$CLAUDE_BIN" >/dev/null 2>&1; then
  echo "ERROR: '$CLAUDE_BIN' not on PATH — install the Claude Code CLI (https://claude.com/claude-code) or set CLAUDE_BIN." >&2
  exit 2
fi
[[ -f "$CASES" ]] || { echo "ERROR: no cases file at $CASES" >&2; exit 2; }

# CLEAN BOX. `--plugin-dir X` ADDS a plugin; it removes nothing already
# installed. Without this, every run also loaded 33 user-scope plugins —
# including a near-copy of the plugin under test — plus every personal skill in
# ~/.claude/skills, one of which is a 22 KB andon-loop containing the very rule
# the oracle asserts. That contamination does not cancel across arms: the
# contaminant IS an andon implementation, so it supplies whatever the weaker
# arm lacks. Set CLEAN_BOX=0 only to deliberately reproduce the old behavior.
CLEAN_BOX="${CLEAN_BOX:-1}"
SETTINGS_FLAGS=()
if [[ "$CLEAN_BOX" == "1" ]]; then
  CLEAN_BOX_JSON="${CLEAN_BOX_JSON:-$(mktemp -t cleanbox).json}"
  if python3 "$HERE/make-clean-box.py" "$CLEAN_BOX_JSON"; then
    SETTINGS_FLAGS=(--settings "$CLEAN_BOX_JSON")
  else
    echo "ERROR: could not build the clean-box settings; refusing to run contaminated." >&2
    exit 2
  fi

  # PROVE isolation before spending tokens on it. make-clean-box.py builds the
  # settings that SHOULD isolate the run, but a documented mandatory guard
  # that nothing ever calls is exactly the "guard that exists and is never
  # called" defect this repo has been burned by before (CLAUDE.md, "Think
  # before deciding"). verify-clean-box.sh actually asks a run which
  # skills/agents it can see and fails if anything beyond the plugin(s) under
  # test leaks in. Escape hatch: SKIP_CLEAN_BOX_VERIFY=1, for callers (e.g.
  # determinism.sh) that already verified the same plugin set this session.
  if [[ "${SKIP_CLEAN_BOX_VERIFY:-0}" != "1" ]]; then
    mapfile -t _cb_plugins < <(awk -F'\t' -v filt="$FILTER" \
      '!/^#/ && NF && (filt=="" || $1==filt) {print $2}' "$CASES" | sort -u)
    if [[ "${#_cb_plugins[@]}" -eq 0 ]]; then
      echo "ERROR: no matching cases to determine which plugin(s) to clean-box-verify (filter='$FILTER')." >&2
      exit 2
    fi
    echo "── verifying clean-box isolation for: ${_cb_plugins[*]}"
    if ! CLAUDE_BIN="$CLAUDE_BIN" bash "$HERE/verify-clean-box.sh" "${_cb_plugins[@]}"; then
      echo "ERROR: clean box is NOT isolated — refusing to run cases against a contaminated box." >&2
      echo "       Set SKIP_CLEAN_BOX_VERIFY=1 to bypass, only if isolation was already verified for this plugin set." >&2
      exit 2
    fi
  fi
fi

pass=0; fail=0; err=0; ran=0
while IFS=$'\t' read -r id plugin fixture prompt artifact regex antiregex; do
  [[ -z "${id:-}" || "$id" == \#* ]] && continue
  [[ -n "$FILTER" && "$FILTER" != "$id" ]] && continue
  ran=$((ran + 1))
  # A missing fixture used to be invisible: `cp` failed, the plugin ran against
  # an EMPTY temp dir, correctly reported "nothing to audit", and the case
  # scored a confident FAIL indistinguishable from a real defect. Three cases
  # reported 0/3 this way after the fixtures were relocated. Missing input is a
  # harness fault, so it is ERROR — never a verdict about the plugin.
  if [[ ! -d "$REPO_ROOT/$fixture" ]]; then
    echo "── [$id] plugin=$plugin  fixture=$fixture"
    echo "   ERROR — fixture directory does not exist: $fixture"
    echo "VERDICT $id ERROR"
    err=$((err + 1)); continue
  fi
  tmp="$(mktemp -d)"
  if ! cp -R "$REPO_ROOT/$fixture/." "$tmp/" 2>/dev/null; then
    echo "── [$id] plugin=$plugin  fixture=$fixture"
    echo "   ERROR — could not copy fixture into the temp cwd"
    echo "VERDICT $id ERROR"
    err=$((err + 1)); rm -rf "$tmp"; continue
  fi
  # A fixture dir IS the target repo the plugin reads, so any file in it
  # describing the seeded defect is an answer key handed straight to the
  # subject under test — it will cite it and "pass" without detecting
  # anything. Keep that documentation in _EXPECTED.md and strip it from the
  # copy, so the plugin has to find the defect from the code/ledger alone.
  rm -f "$tmp/_EXPECTED.md"
  echo "── [$id] plugin=$plugin  fixture=$fixture"
  ( cd "$tmp" && "$CLAUDE_BIN" --plugin-dir "$REPO_ROOT/$plugin" "${SETTINGS_FLAGS[@]}" --print "$prompt" $CLAUDE_PERM_FLAGS ) \
    >"$tmp/.stdout" 2>"$tmp/.stderr"
  rc=$?

  # Preserve the transcript BEFORE any verdict, so a sweep's failures can be
  # adjudicated by reading rather than re-run. Named per (id, epoch, pid).
  if [[ -n "${RUN_LOG_DIR:-}" ]]; then
    mkdir -p "$RUN_LOG_DIR"
    stamp="$id.$(date +%s).$$"
    cp "$tmp/.stdout" "$RUN_LOG_DIR/$stamp.stdout" 2>/dev/null
    [[ -s "$tmp/.stderr" ]] && cp "$tmp/.stderr" "$RUN_LOG_DIR/$stamp.stderr" 2>/dev/null
  fi

  # ERROR is a THIRD verdict, distinct from FAIL. A run that never really
  # happened is evidence about the harness, not about the plugin, and must
  # never be counted as either a pass or a fail. This has now bitten this
  # pilot twice, in two different disguises:
  #   1. empty stdout        — the CLI refused to start under root
  #   2. NON-empty stdout    — "You've hit your session limit · resets 2pm",
  #                            a one-line banner that scored as 5 clean FAILs
  # So checking for 0 bytes is not enough. Three guards, in order of certainty:
  # a known refusal banner, then a substantive-length floor (a real skill
  # report runs to hundreds of bytes; a 60-byte reply did not run the plugin).
  vacuous=""
  if [[ ! -s "$tmp/.stdout" ]]; then
    vacuous="claude produced no stdout"
  elif grep -Eiq '(hit your (session|usage) limit|usage limit reached|resets [0-9]|credit balance is too low|rate.?limit(ed)? |invalid api key|cannot be used with root|please run .?claude login|not logged in)' "$tmp/.stdout"; then
    vacuous="CLI refusal banner: $(head -c 120 "$tmp/.stdout" | tr '\n' ' ')"
  elif [[ "$(wc -c <"$tmp/.stdout")" -lt "${MIN_STDOUT_BYTES:-200}" ]]; then
    vacuous="stdout is only $(wc -c <"$tmp/.stdout" | tr -d ' ') bytes — too short to be a real skill run"
  fi
  if [[ -n "$vacuous" ]]; then
    echo "   ERROR — $vacuous (rc=$rc); harness/process failure, not a plugin verdict"
    [[ -s "$tmp/.stderr" ]] && sed -n '1,5p' "$tmp/.stderr"
    echo "VERDICT $id ERROR"
    err=$((err + 1)); [[ -n "${KEEP_TMP:-}" ]] && echo "   tmp kept: $tmp" || rm -rf "$tmp"; continue
  fi

  target="$tmp/.stdout"
  if [[ "$artifact" != "-" ]]; then
    if [[ -f "$tmp/$artifact" ]]; then
      target="$tmp/$artifact"
    else
      echo "   FAIL — expected artifact not produced: $artifact (claude rc=$rc)"
      echo "VERDICT $id FAIL"
      fail=$((fail + 1)); [[ -n "${KEEP_TMP:-}" ]] && echo "   tmp kept: $tmp" || rm -rf "$tmp"; continue
    fi
  fi

  # An oracle may require SEVERAL patterns to hold at once, joined by @@AND@@.
  # A single ERE cannot express conjunction, but some contract clauses are
  # inherently two-part — e.g. "named the missing required field" AND
  # "declined to act on it" — and collapsing that to one alternation would
  # credit either half alone. Split, and require every part to match.
  missing=""
  saved_ifs="$IFS"; IFS=$'\n'
  for part in $(printf '%s' "$regex" | sed 's/@@AND@@/\n/g'); do
    [[ -z "$part" ]] && continue
    grep -Eiq -- "$part" "$target" || missing="$part"
  done
  IFS="$saved_ifs"

  if [[ -n "$missing" ]]; then
    echo "   FAIL — /$missing/ not found in ${target#"$tmp"/} (claude rc=$rc)"
    [[ -n "${VERBOSE:-}" ]] && sed -n '1,40p' "$target"
    echo "VERDICT $id FAIL"
    fail=$((fail + 1))
  elif [[ -n "${antiregex:-}" ]] && grep -Eiq -- "$antiregex" "$target"; then
    # A must-NOT-match assertion: some contract violations are proven by what
    # the run DID say, not by what it omitted. See cases.tsv for per-case
    # rationale and the known limits of each anti-pattern.
    echo "   FAIL — anti-pattern /$antiregex/ matched in ${target#"$tmp"/} (forbidden behavior observed)"
    [[ -n "${VERBOSE:-}" ]] && grep -Ei -m3 -- "$antiregex" "$target"
    echo "VERDICT $id FAIL"
    fail=$((fail + 1))
  else
    echo "   PASS — all oracle patterns matched in ${target#"$tmp"/}"
    echo "VERDICT $id PASS"
    pass=$((pass + 1))
  fi
  [[ -n "${KEEP_TMP:-}" ]] && echo "   tmp kept: $tmp" || rm -rf "$tmp"
done < "$CASES"

echo "── $pass passed, $fail failed, $err errored, $ran ran"
[[ "$fail" -eq 0 && "$err" -eq 0 && "$ran" -gt 0 ]]
