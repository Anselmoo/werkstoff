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
#
# Exit: 0 iff at least one case ran and none failed; 2 if the CLI is missing.

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

pass=0; fail=0; ran=0
while IFS=$'\t' read -r id plugin fixture prompt artifact regex; do
  [[ -z "${id:-}" || "$id" == \#* ]] && continue
  [[ -n "$FILTER" && "$FILTER" != "$id" ]] && continue
  ran=$((ran + 1))
  tmp="$(mktemp -d)"
  cp -R "$REPO_ROOT/$fixture/." "$tmp/"
  # A fixture dir IS the target repo the plugin reads, so any file in it
  # describing the seeded defect is an answer key handed straight to the
  # subject under test — it will cite it and "pass" without detecting
  # anything. Keep that documentation in _EXPECTED.md and strip it from the
  # copy, so the plugin has to find the defect from the code/ledger alone.
  rm -f "$tmp/_EXPECTED.md"
  echo "── [$id] plugin=$plugin  fixture=$fixture"
  ( cd "$tmp" && "$CLAUDE_BIN" --plugin-dir "$REPO_ROOT/$plugin" --print "$prompt" $CLAUDE_PERM_FLAGS ) \
    >"$tmp/.stdout" 2>"$tmp/.stderr"
  rc=$?
  target="$tmp/.stdout"
  if [[ "$artifact" != "-" ]]; then
    if [[ -f "$tmp/$artifact" ]]; then
      target="$tmp/$artifact"
    else
      echo "   FAIL — expected artifact not produced: $artifact (claude rc=$rc)"
      fail=$((fail + 1)); [[ -n "${KEEP_TMP:-}" ]] && echo "   tmp kept: $tmp" || rm -rf "$tmp"; continue
    fi
  fi
  if grep -Eiq -- "$regex" "$target"; then
    echo "   PASS — matched /$regex/ in ${target#"$tmp"/}"
    pass=$((pass + 1))
  else
    echo "   FAIL — /$regex/ not found in ${target#"$tmp"/} (claude rc=$rc)"
    [[ -n "${VERBOSE:-}" ]] && sed -n '1,40p' "$target"
    fail=$((fail + 1))
  fi
  [[ -n "${KEEP_TMP:-}" ]] && echo "   tmp kept: $tmp" || rm -rf "$tmp"
done < "$CASES"

echo "── $pass passed, $fail failed, $ran ran"
[[ "$fail" -eq 0 && "$ran" -gt 0 ]]
