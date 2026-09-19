#!/usr/bin/env bash
# Reproduce the plan-file-under-lock hazard. No tokens, no agents, no network.
#
# Feeds arbeitsplan's PreToolUse guard the exact payload Claude Code would send, with the
# `plan-under-lock` fixture as the working directory. The fixture carries an open
# run_scope.json, so the guard is armed exactly as it would be mid-run.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
FIXTURE="$HERE/fixtures/plan-under-lock"
GUARD="$REPO/plugins/arbeitsplan/hooks/arbeitsplan_guard.py"

probe() { # label, tool_input JSON
  echo "--- $1"
  printf '{"cwd":"%s","tool_name":"Write","tool_input":%s}' "$FIXTURE" "$2" \
    | python3 "$GUARD" 2>&1 >/dev/null
  echo "exit=$?"
  echo
}

echo "arbeitsplan plan-file hazard, reproduced against $GUARD"
echo
probe "the plan-mode plan file, which lives OUTSIDE the repository" \
      '{"file_path":"'"$HOME"'/.claude/plans/example-plan.md"}'
probe "a path INSIDE the declared writeScope, during a fan-out phase" \
      '{"file_path":"pipeline/score.py"}'
