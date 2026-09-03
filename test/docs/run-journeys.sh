#!/usr/bin/env bash
# Layer 2 of the docs UX test suite: JOURNEY TESTS.
#
# Layer 1 (docs_ux_audit.py) is static and free: it checks claims IN the docs
# against the filesystem. This layer asks a different question entirely --
# given a real user goal, stated in the user's own words, does the
# DOCUMENTATION SITE lead a reader to the right page? That can only be
# measured by putting a fresh model in front of the docs and watching where
# it lands, so this costs real tokens (see README.md for the estimate).
#
# ISOLATION FROM PRIOR KNOWLEDGE -- the load-bearing design decision here.
# If the model under test can answer from its own training/session knowledge
# of werkstoff's plugins, this measures the MODEL, not the DOCS. Two
# independent levers close that gap, both reused from test/plugins/:
#
#   1. A docs-ONLY cwd. Each case runs in a fresh tmp dir containing nothing
#      but an rsync'd copy of docs/ (built dist/ output excluded -- copying
#      the pre-rendered site would hand the model a search index and nav
#      tree it should have to derive itself). No CLAUDE.md, no plugins/, no
#      analysis/, no repo prose exists in that cwd at all.
#   2. The clean-box settings from test/plugins/make-clean-box.py, exactly as
#      run.sh uses them: every installed plugin disabled, every personal
#      skill turned off. This is necessary even here, where no --plugin-dir
#      is ever passed -- without it, a real werkstoff/andon/self-assess
#      install already on this machine would answer the goal by RUNNING a
#      skill instead of by reading the copied docs/ prose, which is exactly
#      the confound test/plugins/make-clean-box.py's own docstring documents.
#
# On top of both, PROMPT_TEMPLATE below explicitly forbids answering from
# prior knowledge and requires the model to name the exact file path it read.
# That third lever is instruction-following, not a sandbox, and is the
# weakest of the three -- see README.md "Residual weaknesses" for what this
# does NOT rule out (a model that ignores the instruction and cites a path
# from memory is not mechanically prevented from doing so; only the docs-only
# cwd and disabled skills make that answer actually ungroundable in fact,
# since a fabricated citation to a real path is still checkable by a human
# reading the transcript this script saves).
#
# Verdicts are PASS / FAIL / ERROR, with the identical meaning test/plugins/
# run.sh gives them: ERROR means the run never really happened (empty stdout,
# a CLI refusal banner, or a reply too short to be a real exploration) and is
# never scored as either a pass or a fail.
#
# Usage:
#   test/docs/run-journeys.sh              # run every case in journeys.tsv
#   test/docs/run-journeys.sh ci-red-jobs  # run one case by id
# Env:
#   CLAUDE_BIN        (default: claude)
#   CLAUDE_PERM_FLAGS (default: --permission-mode bypassPermissions, or
#                      acceptEdits under root -- see test/plugins/run.sh)
#   RUN_LOG_DIR       (default: test/docs/.runs) -- gitignored; every case's
#                      full transcript is saved here, always, so a human can
#                      read any single result without re-running it
#   MIN_STDOUT_BYTES  (default 200) below this, a run is ERROR not FAIL
#   KEEP_TMP=1        keep the per-case docs-only tmp dir instead of removing it
#
# Exit: 0 iff at least one case ran and none failed or errored; 2 if the CLI
# or journeys.tsv is missing.

set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(git -C "$HERE" rev-parse --show-toplevel)"
CASES="$HERE/journeys.tsv"
CLAUDE_BIN="${CLAUDE_BIN:-claude}"
RUN_LOG_DIR="${RUN_LOG_DIR:-$HERE/.runs}"
MIN_STDOUT_BYTES="${MIN_STDOUT_BYTES:-200}"
FILTER="${1:-}"

# shellcheck source=lib-oracle-match.sh
source "$HERE/lib-oracle-match.sh"

if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
  CLAUDE_PERM_FLAGS="${CLAUDE_PERM_FLAGS:---permission-mode acceptEdits}"
else
  CLAUDE_PERM_FLAGS="${CLAUDE_PERM_FLAGS:---permission-mode bypassPermissions}"
fi

if ! command -v "$CLAUDE_BIN" >/dev/null 2>&1; then
  echo "ERROR: '$CLAUDE_BIN' not on PATH -- install the Claude Code CLI or set CLAUDE_BIN." >&2
  exit 2
fi
[[ -f "$CASES" ]] || { echo "ERROR: no cases file at $CASES" >&2; exit 2; }
if [[ ! -d "$REPO_ROOT/docs" ]]; then
  echo "ERROR: no docs/ tree at $REPO_ROOT/docs -- nothing to isolate a copy from." >&2
  exit 2
fi

mkdir -p "$RUN_LOG_DIR"

# Clean-box settings: reused from test/plugins/, not duplicated. See the file
# header above for why this is still required with no --plugin-dir in play.
CLEAN_BOX_JSON="$(mktemp -t docs-journey-cleanbox).json"
if ! python3 "$REPO_ROOT/test/plugins/make-clean-box.py" "$CLEAN_BOX_JSON"; then
  echo "ERROR: could not build the clean-box settings; refusing to run contaminated." >&2
  exit 2
fi

# The fixed prompt wrapper every goal is embedded into. Deliberately generic
# ("say so plainly") rather than handing the model the literal phrase the
# docs use for an honest gap ("No werkstoff fit") -- see journeys.tsv's
# header comment on why the oracle for those two cases requires BOTH a cited
# file AND an honesty signal, not either alone.
read -r -d '' PROMPT_PREFIX <<'EOF' || true
You are looking only at documentation files inside the current working directory (a
copied docs/ tree from a Claude Code plugin repository). Do not use any prior knowledge
you might have about this repository, its plugins, Superpowers, or Claude Code plugins
in general -- answer using ONLY what you find by reading files under this directory. Do
not read or reference any file outside the current working directory.

A user has this goal, in their own words:

  "
EOF
read -r -d '' PROMPT_SUFFIX <<'EOF' || true
  "

Explore this docs/ tree (Read/Glob/Grep) to find the single page that best tells this
user what to do next. Then answer with:
1. The exact file path, relative to this directory, of the page you found.
2. One sentence quoting or closely paraphrasing the part of that page that answers the
   goal.
3. If, after actually searching, no page in this tree addresses the goal, say so plainly
   instead of forcing an unrelated page onto it -- name the page that comes closest and
   explain concretely why it does not fit, rather than staying silent about it.

Do not state a file path you have not actually opened and read.
EOF

pass=0; fail=0; err=0; ran=0
while IFS=$'\t' read -r id category expected goal regex antiregex; do
  [[ -z "${id:-}" || "$id" == \#* ]] && continue
  [[ -n "$FILTER" && "$FILTER" != "$id" ]] && continue
  ran=$((ran + 1))

  prompt="${PROMPT_PREFIX}${goal}${PROMPT_SUFFIX}"

  tmp="$(mktemp -d)"
  mkdir -p "$tmp/docs"
  # Exclude .vitepress/dist: it is generated build output (the rendered site
  # + a prebuilt search index), and copying it would hand the model a
  # navigation shortcut a reader consulting the SOURCE prose does not get.
  # Excluding it also means this never races with a concurrent
  # `npm run docs:build` writing into the real docs/.vitepress/dist.
  # A failed or partial copy must NEVER reach `claude --print`. This script runs
  # under `set -uo pipefail` with no `-e`, so an rsync failure would otherwise
  # fall straight through and the model would explore an empty or half-populated
  # docs tree; the run would then score FAIL and read as a findability verdict
  # about the docs, when it is really a verdict about the harness. That is
  # exactly the "code that looks correct and silently does nothing" shape
  # CLAUDE.md catalogues, so the copy is checked three ways and any failure is
  # classified ERROR -- missing data -- on the same terms as an empty stdout.
  copy_err=""
  # `$?` is captured on its own line, NOT inside `if ! rsync ...; then`: in that
  # form `$?` holds the status of the negation (always 0 in the taken branch),
  # so the message would report "rsync exited 0" for every failure. Measured --
  # the first version of this guard did exactly that.
  rsync -a --exclude '.vitepress/dist' "$REPO_ROOT/docs/" "$tmp/docs/" 2>"$tmp/.rsync.err"
  rsync_rc=$?
  if [[ "$rsync_rc" -ne 0 ]]; then
    copy_err="rsync exited $rsync_rc copying docs/ into the isolation dir: $(tr '\n' ' ' <"$tmp/.rsync.err" | head -c 200)"
  elif [[ ! -f "$tmp/docs/index.md" ]]; then
    # rsync can exit 0 having copied nothing useful. index.md is the docs root
    # and its absence means the model would start from nowhere.
    copy_err="the copied tree has no docs/index.md -- the isolation dir is empty or partial"
  else
    copied=$(find "$tmp/docs" -name '*.md' -type f | wc -l | tr -d ' ')
    source_count=$(find "$REPO_ROOT/docs" -name '*.md' -type f -not -path '*/.vitepress/dist/*' | wc -l | tr -d ' ')
    if [[ "$copied" -ne "$source_count" ]]; then
      copy_err="copied $copied markdown files but the source has $source_count -- partial copy"
    fi
  fi
  if [[ -n "$copy_err" ]]; then
    echo "── [$id] category=$category  expected=$expected"
    echo "   ERROR — $copy_err; harness failure, not a findability verdict"
    echo "VERDICT $id ERROR"
    err=$((err + 1)); [[ -n "${KEEP_TMP:-}" ]] && echo "   tmp kept: $tmp" || rm -rf "$tmp"; continue
  fi

  echo "── [$id] category=$category  expected=$expected"
  ( cd "$tmp" && "$CLAUDE_BIN" --settings "$CLEAN_BOX_JSON" --print "$prompt" $CLAUDE_PERM_FLAGS ) \
    >"$tmp/.stdout" 2>"$tmp/.stderr"
  rc=$?

  stamp="$id.$(date +%s).$$"
  cp "$tmp/.stdout" "$RUN_LOG_DIR/$stamp.stdout" 2>/dev/null
  [[ -s "$tmp/.stderr" ]] && cp "$tmp/.stderr" "$RUN_LOG_DIR/$stamp.stderr" 2>/dev/null
  {
    echo "id: $id"
    echo "category: $category"
    echo "expected_path: $expected"
    echo "goal: $goal"
    echo "regex: $regex"
    echo "antiregex: ${antiregex:-<none>}"
    echo "claude rc: $rc"
  } > "$RUN_LOG_DIR/$stamp.meta"

  # ERROR classification, identical criteria to test/plugins/run.sh: a run
  # that never really happened is evidence about the harness, never a
  # verdict about the docs.
  vacuous=""
  if [[ ! -s "$tmp/.stdout" ]]; then
    vacuous="claude produced no stdout"
  elif grep -Eiq '(hit your (session|usage) limit|usage limit reached|resets [0-9]|credit balance is too low|rate.?limit(ed)? |invalid api key|cannot be used with root|please run .?claude login|not logged in)' "$tmp/.stdout"; then
    vacuous="CLI refusal banner: $(head -c 120 "$tmp/.stdout" | tr '\n' ' ')"
  elif [[ "$(wc -c <"$tmp/.stdout")" -lt "$MIN_STDOUT_BYTES" ]]; then
    vacuous="stdout is only $(wc -c <"$tmp/.stdout" | tr -d ' ') bytes -- too short to be a real exploration"
  fi
  if [[ -n "$vacuous" ]]; then
    echo "   ERROR — $vacuous (rc=$rc); harness/process failure, not a findability verdict"
    echo "   transcript: $RUN_LOG_DIR/$stamp.stdout"
    echo "VERDICT $id ERROR"
    err=$((err + 1)); [[ -n "${KEEP_TMP:-}" ]] && echo "   tmp kept: $tmp" || rm -rf "$tmp"; continue
  fi

  verdict_line="$(oracle_verdict "$tmp/.stdout" "$regex" "$antiregex")"
  if [[ "$verdict_line" == PASS ]]; then
    echo "   PASS — all oracle patterns matched"
    echo "VERDICT $id PASS"
    pass=$((pass + 1))
  else
    echo "   FAIL — $verdict_line (claude rc=$rc)"
    echo "   transcript: $RUN_LOG_DIR/$stamp.stdout"
    echo "VERDICT $id FAIL"
    fail=$((fail + 1))
  fi
  [[ -n "${KEEP_TMP:-}" ]] && echo "   tmp kept: $tmp" || rm -rf "$tmp"
done < "$CASES"

rm -f "$CLEAN_BOX_JSON"

echo
echo "── $pass passed, $fail failed, $err errored, $ran ran"
echo "── transcripts saved under $RUN_LOG_DIR"
if [[ "$err" -gt 0 ]]; then
  echo "── $err case(s) errored: no pass rate is reported. An error is missing data,"
  echo "   not a verdict -- fix the harness/CLI issue (see transcripts above) and rerun"
  echo "   just those case ids before trusting any number here."
elif [[ "$ran" -gt 0 ]]; then
  eligible=$((pass + fail))
  pct=$(( eligible > 0 ? pass * 100 / eligible : 0 ))
  echo "── pass rate: $pass/$eligible ($pct%) -- a rate over one pass, not a verdict;"
  echo "   see README.md before treating a single sweep as a real number"
fi

[[ "$fail" -eq 0 && "$err" -eq 0 && "$ran" -gt 0 ]]
