#!/usr/bin/env bash
# run_matrix.sh -- a for-loop harness around `claude -p`.
#
# usage: run_matrix.sh --matrix FILE [--out DIR] [--dry-run] [--allow-nested]
#        run_matrix.sh --selftest
#        (add --skip-probe to bypass the one-call authentication preflight)
#        run_matrix.sh --help
#
# Runs the cartesian product of CASES x MODELS x PLUGIN-STATES x REPEATS, one
# fresh `claude -p` process per cell, and records every cell to disk. See
# references/matrix-schema.md for the schema and the design rationale.
#
# WHY A FRESH PROCESS PER CELL. Claude Code builds its skill/agent registry once,
# at session start, so a just-edited skill is invisible until a reload. A fresh
# process is also the only place where `--model` cannot be silently inherited
# from the caller -- the failure delegation.md names as "an omitted model
# inherits your session's model, which silently defeats this section". In a
# matrix cell that inheritance is structurally impossible.
#
# AUTHENTICATION IS PROBED, NOT ASSUMED. An earlier version refused outright
# whenever it detected a nested Claude Code session, on the strength of a
# measurement made in another repository. That does not reproduce here. The
# script now makes one cheap call first: if it authenticates, the sweep runs;
# if not, it refuses AND PRINTS WHAT THE PROBE ACTUALLY GOT, which the blanket
# refusal never could. --skip-probe bypasses it.
#
# STDLIB ONLY: bash + a bare system python3 for JSON. No jq dependency.

set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MATRIX=""
OUT=""
DRY_RUN=0
SKIP_PROBE=0
PROBE_OUTPUT=""
SELFTEST=0
CLAUDE_BIN="${CLAUDE_BIN:-claude}"

# The tool surface a cell may legitimately reach. Denying is BEST-EFFORT and
# will go stale -- that is not a flaw to be fixed by curating it harder, it is
# why EXPECTED_TOOLS (asserted after the fact, from the matrix) exists.
DEFAULT_DISALLOWED="Bash,BashOutput,KillShell,Read,Write,Edit,NotebookEdit,NotebookRead,Glob,Grep,LSP,WebFetch,WebSearch,Monitor,DesignSync,RemoteTrigger,Agent,Task,SendMessage,ListAgents,TaskOutput,TaskStop,Workflow,CronCreate,CronDelete,CronList,ScheduleWakeup,PushNotification,ListMcpResourcesTool,ReadMcpResourceTool,ReadMcpResourceDirTool,Artifact,SendUserFile,ReportFindings,AskUserQuestion,ListPlugins,SearchPlugins,SuggestPluginInstall,SearchSkills,SuggestSkills,EnterWorktree,ExitWorktree,EnterPlanMode,ExitPlanMode,SlashCommand,TodoWrite"

usage() { sed -n '2,30p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; }

die() { echo "run_matrix.sh: $*" >&2; exit 2; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --matrix) MATRIX="${2:-}"; shift 2 ;;
    --out) OUT="${2:-}"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    --skip-probe) SKIP_PROBE=1; shift ;;
    --allow-nested) SKIP_PROBE=1; shift ;;  # deprecated alias, kept so old commands still work
    --selftest) SELFTEST=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) die "unknown argument '$1' (try --help)" ;;
  esac
done

# ---------------------------------------------------------------------------
# Authentication preflight -- a PROBE, not a guess about the environment.
#
# This used to be a blanket refusal whenever CLAUDECODE or CLAUDE_CODE_ENTRYPOINT
# was set, on the strength of a measurement made in a DIFFERENT repository on a
# different day ("a nested `claude -p` fails: OAuth session expired"). That
# measurement does not reproduce here -- a nested `claude -p` authenticates
# fine -- and importing someone else's result as a law, in a repository whose
# CLAUDE.md says "verify the instrument before trusting its verdict", was the
# error. The refusal was also redundant: a cell that hits an auth banner is
# already scored UNMEASURED with the reason, which is strictly more information
# than refusing to start.
#
# So: ask the question instead of assuming the answer. One cheap call. If it
# authenticates, run; if it does not, refuse WITH THE ACTUAL ERROR, which is
# something a blanket refusal could never print.
# ---------------------------------------------------------------------------
auth_probe() {
  local out rc
  out="$("$CLAUDE_BIN" -p "Reply with exactly: OK" --model haiku \
          --permission-mode plan </dev/null 2>&1)"
  rc=$?
  PROBE_OUTPUT="$out"
  [[ $rc -eq 0 ]] || return 1
  [[ -n "${out// /}" ]] || return 1
  ! grep -qiE 'failed to authenticate|oauth session expired|usage limit|not logged in|invalid api key' <<<"$out"
}

# ---------------------------------------------------------------------------
# Matrix loading and validation, in python3 (no jq dependency).
# ---------------------------------------------------------------------------
read -r -d '' VALIDATE_PY <<'PYEOF' || true
import json, sys, itertools

DEFAULT_EXPECTED = ["Skill", "ToolSearch"]
VALID_ABLATION = {"isolated", "installed"}
VALID_PERM = {"acceptEdits", "auto", "bypassPermissions", "manual", "dontAsk", "plan"}

def fail(msg):
    print("MATRIXERROR " + msg)
    sys.exit(0)

try:
    with open(sys.argv[1]) as fh:
        m = json.load(fh)
except FileNotFoundError:
    fail("no such matrix file: %s" % sys.argv[1])
except json.JSONDecodeError as exc:
    fail("matrix is not valid JSON: %s" % exc)

if not isinstance(m, dict):
    fail("matrix must be a JSON object")

# `allowed_tools` is refused rather than honoured: it is a PERMISSION allowlist
# and does not reduce the tool surface. Honouring it quietly would hand back a
# sweep whose isolation claim is false.
if "allowed_tools" in m:
    fail("'allowed_tools' is not supported: it is a permission allowlist and does "
         "NOT restrict the tool surface. Use 'disallowed_tools' (and rely on "
         "'expected_tools' for the assertion that actually gates).")

for key in ("cases", "models", "plugin_states"):
    if key not in m:
        fail("missing required key %r" % key)

cases = m["cases"]
if not isinstance(cases, list) or not cases:
    fail("'cases' must be a non-empty list")
ids = set()
for i, c in enumerate(cases):
    if not isinstance(c, dict):
        fail("cases[%d] must be an object" % i)
    if not c.get("id"):
        fail("cases[%d] has no 'id'" % i)
    if c["id"] in ids:
        fail("duplicate case id %r" % c["id"])
    ids.add(c["id"])
    if not c.get("prompt"):
        fail("cases[%d] (%s) has no 'prompt'" % (i, c["id"]))
    if "expect_exit" in c and not isinstance(c["expect_exit"], int):
        fail("cases[%d].expect_exit must be an integer" % i)

models = m["models"]
if not isinstance(models, list) or not models or not all(isinstance(x, str) and x for x in models):
    fail("'models' must be a non-empty list of strings")

states = m["plugin_states"]
if not isinstance(states, list) or not states:
    fail("'plugin_states' must be a non-empty list")
sids = set()
for i, s in enumerate(states):
    if not isinstance(s, dict) or not s.get("id"):
        fail("plugin_states[%d] needs an 'id'" % i)
    if s["id"] in sids:
        fail("duplicate plugin_state id %r" % s["id"])
    sids.add(s["id"])
    pd = s.get("plugin_dir")
    if pd is not None and not isinstance(pd, (str, list)):
        fail("plugin_states[%d].plugin_dir must be a string, a list, or null" % i)
    if isinstance(pd, str) and not pd:
        fail("plugin_states[%d].plugin_dir must not be an empty string" % i)

repeats = m.get("repeats", 1)
if not isinstance(repeats, int) or repeats < 1:
    fail("'repeats' must be an integer >= 1")

ablation = m.get("ablation", "isolated")
if ablation not in VALID_ABLATION:
    fail("'ablation' must be one of %s" % sorted(VALID_ABLATION))

perm = m.get("permission_mode", "plan")
if perm not in VALID_PERM:
    fail("'permission_mode' must be one of %s" % sorted(VALID_PERM))

timeout = m.get("timeout_s", 900)
if not isinstance(timeout, int) or timeout < 1:
    fail("'timeout_s' must be a positive integer")

expected = m.get("expected_tools", DEFAULT_EXPECTED)
if not isinstance(expected, list) or not all(isinstance(x, str) for x in expected):
    fail("'expected_tools' must be a list of strings")

disallowed = m.get("disallowed_tools")
if disallowed is not None:
    if not isinstance(disallowed, list) or not all(isinstance(x, str) for x in disallowed):
        fail("'disallowed_tools' must be a list of strings")
    disallowed = ",".join(disallowed)
else:
    disallowed = ""

if sys.argv[2] == "header":
    # These lines are consumed by `eval` in the shell below, so every value that
    # comes from the matrix FILE is shell-quoted here. Unquoted, an
    # expected_tools or output_format entry containing `;` or `$(...)` ran as
    # shell code before the sweep started -- a matrix file is authored by hand,
    # which makes it a footgun rather than an exploit, but the whole point of
    # this script is that a quoting mistake here is invisible and produces a
    # clean-looking table. The %d fields cannot carry metacharacters and are
    # left alone.
    import shlex

    print("OK")
    print("repeats=%d" % repeats)
    print("ablation=%s" % shlex.quote(str(ablation)))
    print("permission_mode=%s" % shlex.quote(str(perm)))
    print("timeout_s=%d" % timeout)
    print("output_format=%s" % shlex.quote(str(m.get("output_format", "json"))))
    print("strict_mcp=%d" % (1 if m.get("strict_mcp_config", True) else 0))
    print("expected_tools=%s" % shlex.quote(",".join(expected)))
    print("disallowed_tools=%s" % shlex.quote(disallowed))
    print("cells=%d" % (len(cases) * len(models) * len(states) * repeats))
    sys.exit(0)

# One line per cell, fields separated by 0x1E (RECORD SEPARATOR) and plugin
# dirs joined by 0x1F (UNIT SEPARATOR).
#
# NOT tab. Tab is an IFS *whitespace* character in bash, so `IFS=$'\t' read`
# collapses a run of tabs into one delimiter and drops empty fields entirely --
# every field after an empty one shifts left by one. The plugin-absent arm has
# an empty plugin_dir, so with tabs the PROMPT slid into the plugin_dir slot and
# the two ablation arms came out SWAPPED: the enabled arm ran with no plugin and
# the disabled arm ran with `--plugin-dir "<the prompt>"`. The sweep still
# produced a tidy table of PASSes; it was measuring nothing. 0x1E is not an IFS
# whitespace character, so empty fields survive.
for c, mo, s, n in itertools.product(cases, models, states, range(1, repeats + 1)):
    pd = s.get("plugin_dir")
    dirs = [] if pd is None else ([pd] if isinstance(pd, str) else list(pd))
    print("\x1e".join([
        c["id"], mo, s["id"], str(n), str(c.get("expect_exit", 0)),
        "\x1f".join(dirs),
        c["prompt"].replace("\x1e", " ").replace("\x1f", " ").replace("\n", " "),
    ]))
PYEOF

# ---------------------------------------------------------------------------
# --selftest: validation only, never runs a cell.
# ---------------------------------------------------------------------------
if [[ "$SELFTEST" -eq 1 ]]; then
  tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT
  fails=0
  probe () { # name, json, expect(ok|err)
    printf '%s' "$2" > "$tmp/m.json"
    out="$(python3 -c "$VALIDATE_PY" "$tmp/m.json" header 2>&1)"
    if [[ "$3" == "ok" ]]; then
      if [[ "$out" == OK* ]]; then echo "  ok   $1"; else echo "  FAIL $1: $out"; fails=$((fails+1)); fi
    else
      if [[ "$out" == MATRIXERROR* ]]; then echo "  ok   $1"; else echo "  FAIL $1: expected rejection, got: $out"; fails=$((fails+1)); fi
    fi
  }
  GOOD='{"cases":[{"id":"c","prompt":"p"}],"models":["sonnet"],"plugin_states":[{"id":"with","plugin_dir":"d"},{"id":"without","plugin_dir":null}],"repeats":3}'
  probe "valid matrix"                    "$GOOD" ok
  probe "missing cases"                   '{"models":["s"],"plugin_states":[{"id":"a"}]}' err
  probe "empty cases"                     '{"cases":[],"models":["s"],"plugin_states":[{"id":"a"}]}' err
  probe "case without prompt"             '{"cases":[{"id":"c"}],"models":["s"],"plugin_states":[{"id":"a"}]}' err
  probe "duplicate case ids"              '{"cases":[{"id":"c","prompt":"p"},{"id":"c","prompt":"q"}],"models":["s"],"plugin_states":[{"id":"a"}]}' err
  probe "duplicate plugin_state ids"      '{"cases":[{"id":"c","prompt":"p"}],"models":["s"],"plugin_states":[{"id":"a"},{"id":"a"}]}' err
  probe "repeats zero"                    '{"cases":[{"id":"c","prompt":"p"}],"models":["s"],"plugin_states":[{"id":"a"}],"repeats":0}' err
  probe "bad ablation"                    '{"cases":[{"id":"c","prompt":"p"}],"models":["s"],"plugin_states":[{"id":"a"}],"ablation":"sideways"}' err
  probe "bad permission_mode"             '{"cases":[{"id":"c","prompt":"p"}],"models":["s"],"plugin_states":[{"id":"a"}],"permission_mode":"yolo"}' err
  probe "allowed_tools is REFUSED"        '{"cases":[{"id":"c","prompt":"p"}],"models":["s"],"plugin_states":[{"id":"a"}],"allowed_tools":["Skill"]}' err
  probe "empty plugin_dir string"         '{"cases":[{"id":"c","prompt":"p"}],"models":["s"],"plugin_states":[{"id":"a","plugin_dir":""}]}' err
  probe "not json"                        'not json at all' err

  printf '%s' "$GOOD" > "$tmp/m.json"
  n="$(python3 -c "$VALIDATE_PY" "$tmp/m.json" cells | wc -l | tr -d ' ')"
  if [[ "$n" == "6" ]]; then echo "  ok   cell expansion 1x1x2x3 = 6"; else echo "  FAIL cell expansion: got $n, want 6"; fails=$((fails+1)); fi

  # ---- end-to-end, against a STUB cli -------------------------------
  # Validation alone would not have caught either of the two bugs this block
  # exists for. Both were in the bash that builds a cell's argv, both dropped
  # data silently, and both still produced a full table of PASSes:
  #   1. tab as the field separator -- an IFS *whitespace* char, so the empty
  #      plugin_dir of the disabled arm collapsed and every later field shifted
  #      left, SWAPPING the two ablation arms.
  #   2. printf '%s' with no trailing newline -- `read` hit EOF, the loop body
  #      never ran, and the ENABLED arm got no --plugin-dir at all.
  # An ablation whose arms are wrong is worse than no ablation, because it
  # reports a number. These assertions are the only thing standing between that
  # and a green run.
  stub="$tmp/stub-claude"
  cat > "$stub" <<'STUB'
#!/usr/bin/env bash
echo '{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Skill"}]}}'
echo '{"type":"result","result":"A reply long enough to clear the 200-byte floor that separates a real answer from a refusal banner, so the cell is scored rather than discarded as unmeasured."}'
STUB
  chmod +x "$stub"
  cat > "$tmp/e2e.json" <<STUBM
{"cases":[{"id":"c","prompt":"do the thing","expect_exit":0}],
 "models":["sonnet"],
 "plugin_states":[{"id":"with","plugin_dir":"$HERE/.."},{"id":"without","plugin_dir":null}],
 "repeats":2,"ablation":"isolated","timeout_s":30}
STUBM
  # Keep the sub-run's output: a selftest that fails without showing why sends
  # the reader back here to re-run it by hand, which is the moment they stop.
  CLAUDE_BIN="$stub" bash "${BASH_SOURCE[0]}" --matrix "$tmp/e2e.json" \
      --out "$tmp/e2e-out" --allow-nested >"$tmp/e2e.log" 2>&1
  e2e_rc=$?
  e2e="$(OUTDIR="$tmp/e2e-out" python3 - <<'E2E'
import json, os, pathlib
bad = []
cells = sorted((pathlib.Path(os.environ["OUTDIR"]) / "cells").glob("*.json"))
if len(cells) != 4:
    bad.append("expected 4 cells, got %d" % len(cells))
for p in cells:
    c = json.loads(p.read_text()); argv = c["argv"]; arm = c["plugin_state"]
    pd = argv[argv.index("--plugin-dir") + 1] if "--plugin-dir" in argv else None
    if arm == "with" and pd is None:
        bad.append("%s: ENABLED arm has no --plugin-dir" % c["label"])
    if arm == "without" and pd is not None:
        bad.append("%s: DISABLED arm carries --plugin-dir %r" % (c["label"], pd))
    for flag in ("--setting-sources", "--strict-mcp-config", "--disallowedTools", "--model"):
        if flag not in argv:
            bad.append("%s: missing %s" % (c["label"], flag))
    if "--allowedTools" in argv:
        bad.append("%s: uses --allowedTools, which does not restrict" % c["label"])
    if c["outcome"] != "PASS":
        bad.append("%s: outcome %s, wanted PASS" % (c["label"], c["outcome"]))
print("; ".join(bad) if bad else "OK")
E2E
)"
  if [[ "$e2e" == "OK" ]]; then
    echo "  ok   end-to-end argv: arms correct, isolation flags present"
  else
    echo "  FAIL end-to-end argv: $e2e (sub-run exit $e2e_rc)"
    sed 's/^/         | /' "$tmp/e2e.log" | head -12
    fails=$((fails+1))
  fi

  # An infrastructure failure must be UNMEASURED, never FAIL, and must leave a
  # zero denominator -- otherwise the breaker downstream measures the weather.
  cat > "$tmp/stub-broken" <<'BROKEN'
#!/usr/bin/env bash
echo "Failed to authenticate: OAuth session expired and could not be refreshed" >&2
exit 1
BROKEN
  chmod +x "$tmp/stub-broken"
  CLAUDE_BIN="$tmp/stub-broken" bash "${BASH_SOURCE[0]}" --matrix "$tmp/e2e.json" \
      --out "$tmp/broken-out" --allow-nested >"$tmp/broken.log" 2>&1
  broke="$(OUTDIR="$tmp/broken-out" python3 - <<'BRK'
import json, os, pathlib
s = json.loads((pathlib.Path(os.environ["OUTDIR"]) / "summary.json").read_text())
bad = []
if set(s["tally"]) != {"UNMEASURED"}:
    bad.append("tally %r, wanted only UNMEASURED" % s["tally"])
if any(r["measured"] != 0 for r in s["rows"]):
    bad.append("a broken arm reported a non-zero denominator")
print("; ".join(bad) if bad else "OK")
BRK
)"
  if [[ "$broke" == "OK" ]]; then echo "  ok   infrastructure failure -> UNMEASURED, denominator 0"; else echo "  FAIL infrastructure failure: $broke"; fails=$((fails+1)); fi

  # A missing plugin_dir on the enabled arm must stop the SCRIPT, not just the
  # loop. While the cell list was piped into `while`, the loop ran in a subshell
  # and `exit 2` killed only that: the script went on to write a summary and
  # exited 0, reporting a sweep that never ran. Measured both ways before the
  # fix -- exit 0 with a summary, versus exit 2 with none.
  bd="$(mktemp -d)"
  cat > "$bd/m.json" <<'BADDIR'
{"cases":[{"id":"c","prompt":"hi"}],"models":["haiku"],
 "plugin_states":[{"id":"on","plugin_dir":"/definitely/not/here"}],
 "repeats":1,"ablation":"isolated","expected_tools":["Skill"]}
BADDIR
  CLAUDE_BIN="$stub" bash "$0" --matrix "$bd/m.json" --out "$bd/out" --allow-nested >/dev/null 2>&1
  rc_bad=$?
  if [[ "$rc_bad" -eq 2 && ! -f "$bd/out/summary.json" ]]; then
    echo "  ok   a missing plugin_dir exits the script, and writes no summary"
  else
    echo "  FAIL missing plugin_dir: exit $rc_bad, summary $([ -f "$bd/out/summary.json" ] && echo written || echo absent) -- wanted exit 2 and no summary"
    fails=$((fails+1))
  fi
  rm -rf "$bd"

  # ---- the stdin-consumption regression -----------------------------
  # THE case the other stubs cannot catch. A real `claude -p` reads stdin;
  # the cell loop reads its cell list FROM stdin. Without `< /dev/null` on the
  # child, the first cell's process eats the rest of the list and the sweep
  # silently runs a subset while reporting a clean tally over it. The stub
  # below reads stdin exactly the way the real binary does, so it reproduces
  # the bug in a fraction of a second and for no tokens.
  #
  # Assert on CELL COUNT, never on the tally: the bug's whole signature was a
  # tidy "PASS 1/1" over half an experiment.
  cat > "$tmp/stub-greedy" <<'GREEDY'
#!/usr/bin/env bash
cat > /dev/null            # <- consumes whatever stdin it is given
echo '{"type":"result","result":"A reply long enough to clear the two hundred byte floor that separates a scored answer from a refusal banner, so this cell is measured rather than discarded."}'
GREEDY
  chmod +x "$tmp/stub-greedy"
  CLAUDE_BIN="$tmp/stub-greedy" bash "${BASH_SOURCE[0]}" --matrix "$tmp/e2e.json" \
      --out "$tmp/greedy-out" --skip-probe >"$tmp/greedy.log" 2>&1
  greedy="$(OUTDIR="$tmp/greedy-out" python3 - <<'GRD'
import json, os, pathlib
d = pathlib.Path(os.environ["OUTDIR"]) / "cells"
n = len(list(d.glob("*.json"))) if d.exists() else 0
print("OK" if n == 4 else "a stdin-reading child ate the cell list: %d of 4 cells ran" % n)
GRD
)"
  if [[ "$greedy" == "OK" ]]; then
    echo "  ok   stdin-reading child does not eat the cell list"
  else
    echo "  FAIL $greedy"
    fails=$((fails+1))
  fi

  echo
  if [[ "$fails" -gt 0 ]]; then echo "SELFTEST FAILED ($fails)"; exit 1; fi
  echo "selftest passed (13 validation + 3 end-to-end against stubs; no real cells run)"
  exit 0
fi

# ---------------------------------------------------------------------------
# Real run.
# ---------------------------------------------------------------------------
[[ -n "$MATRIX" ]] || die "--matrix FILE is required (try --help)"
command -v python3 >/dev/null 2>&1 || die "python3 is required for JSON parsing"
command -v "$CLAUDE_BIN" >/dev/null 2>&1 || die "'$CLAUDE_BIN' is not on PATH (set CLAUDE_BIN)"

# Probe once, before spending a sweep. A sweep whose every cell comes back
# UNMEASURED for the same reason is an expensive way to learn one fact.
if [[ "$DRY_RUN" -eq 0 && "$SKIP_PROBE" -eq 0 ]]; then
  printf 'auth probe       : '
  if auth_probe; then
    echo "ok"
  else
    echo "FAILED"
    cat >&2 <<PROBEFAIL

run_matrix.sh: '$CLAUDE_BIN' could not complete a one-line call, so every cell
would record the same failure. Refusing to spend a sweep on it.

What the probe got back:
$(printf '%s\n' "$PROBE_OUTPUT" | head -12 | sed 's/^/    /')

Fix the environment and re-run, or pass --skip-probe if you know better than
the probe does. Note that a cell which fails this way is scored UNMEASURED and
excluded from every denominator -- it is never a FAIL, because nothing about
the work was measured.
PROBEFAIL
    exit 3
  fi
fi

HEADER="$(python3 -c "$VALIDATE_PY" "$MATRIX" header)"
if [[ "$HEADER" == MATRIXERROR* ]]; then
  echo "${HEADER#MATRIXERROR }" >&2
  exit 2
fi
eval "$(echo "$HEADER" | tail -n +2)"

OUT="${OUT:-analysis/arbeitsplan/matrix-$(date +%Y%m%d-%H%M%S)}"
mkdir -p "$OUT/cells" || die "cannot create $OUT"

echo "matrix          : $MATRIX"
echo "cells           : $cells  (repeats=$repeats)"
echo "ablation        : $ablation"
echo "expected tools  : $expected_tools"
echo "output          : $OUT"
echo

# `timeout` is GNU coreutils and is NOT on a stock macOS -- it arrives only via
# homebrew, as `timeout` or `gtimeout`. Without this resolution the script works
# on the author's machine and dies on a clean one, which is the least useful
# possible place to discover a dependency. With neither available we run
# UNTIMED and say so, rather than silently dropping the per-cell ceiling: a
# hung cell would otherwise stall the whole sweep with no explanation.
TIMEOUT_BIN=""
if command -v timeout >/dev/null 2>&1; then TIMEOUT_BIN="timeout"
elif command -v gtimeout >/dev/null 2>&1; then TIMEOUT_BIN="gtimeout"
else
  echo "warning: neither 'timeout' nor 'gtimeout' found -- cells run UNTIMED." >&2
  echo "         install coreutils (brew install coreutils) to enforce timeout_s=${timeout_s}." >&2
fi

DISALLOWED="${disallowed_tools:-}"
[[ -n "$DISALLOWED" ]] || DISALLOWED="$DEFAULT_DISALLOWED"

# `done < <(...)` rather than `... | while`. A pipeline runs the loop in a
# SUBSHELL, so the `exit 2` below for a missing plugin_dir terminated only that
# subshell: the script carried on, wrote an empty summary and exited 0, reporting
# a sweep that never ran. Process substitution keeps the loop in this shell, so
# the exit is the script's. It also means counters set in the loop survive it.
while IFS=$'\x1e' read -r cid model sid n expect dirs prompt; do
  label="${cid}__${model}__${sid}__${n}"
  cell_json="$OUT/cells/${label}.json"

  argv=("$CLAUDE_BIN" -p "$prompt" --model "$model"
        --permission-mode "$permission_mode"
        --output-format "$output_format"
        --disallowedTools "$DISALLOWED")
  if [[ "$ablation" == "isolated" ]]; then
    argv+=(--setting-sources project)
    [[ "${strict_mcp:-1}" == "1" ]] && argv+=(--strict-mcp-config)
  fi
  # printf '%s\n', not printf '%s'. Without the trailing newline `read` hits EOF
  # on the final line, returns non-zero and the loop body never runs -- so a
  # single-entry plugin_dir silently produced NO --plugin-dir flag at all, and
  # the "enabled" arm ran with the plugin absent. The sweep still printed a
  # table of PASSes. Second data-dropping bash idiom in these six lines; the
  # first was tab as an IFS whitespace character, above.
  #
  # The `cd` runs in the ORIGINAL working directory (each cell is executed in
  # its own temp dir later), so a relative plugin_dir resolves against the repo
  # the operator invoked this from, which is what they mean by it.
  # Split on 0x1F with bash's own ANSI-C quoting, NOT with `tr '\x1f' '\n'`.
  # tr understands OCTAL escapes (\037) and not hex, so '\x1f' is read as the
  # character SET {backslash, x, 1, f} -- it replaced every f, x and 1 in the
  # path with a newline, shredding /...werkstoff/... into five fragments and
  # then reporting the first as a missing directory. Same trap as the [^\n]
  # bracket expression in this repo's CLAUDE.md defect table, one layer down.
  # $'\x1f' in bash IS a real hex escape, and 0x1F is not IFS whitespace, so
  # empty entries survive rather than collapsing.
  if [[ -n "$dirs" ]]; then
    IFS=$'\x1f' read -ra _dir_list <<< "$dirs"
    for d in "${_dir_list[@]}"; do
      [[ -n "$d" ]] || continue
      abs="$(cd "$d" 2>/dev/null && pwd)"
      if [[ -z "$abs" ]]; then
        echo "run_matrix.sh: plugin_dir '$d' does not exist -- refusing to run a sweep whose enabled arm loads nothing." >&2
        exit 2
      fi
      argv+=(--plugin-dir "$abs")
    done
  fi

  if [[ "$DRY_RUN" -eq 1 ]]; then
    printf '%-38s ' "$label"; printf '%q ' "${argv[@]}"; echo
    continue
  fi

  # Each cell runs in its OWN empty directory. Combined with
  # --setting-sources project this is what makes the isolation structural
  # rather than an enumeration of everything installed today: there is no
  # project settings file, no CLAUDE.md and no personal skill to find.
  celldir="$(mktemp -d)"
  start="$(date +%s)"
  stdout_file="$OUT/cells/${label}.stdout"
  # `< /dev/null` is LOAD-BEARING, not hygiene. This loop reads its cell list
  # from a pipe on stdin; `claude -p` inherits that stdin and consumes what is
  # left of it. Without the redirect a 2-arm sweep ran ONE arm and reported
  # "PASS 1/1" -- a confident number over half an experiment. Proof:
  #   printf 'a\nb\nc\n' | while read -r r; do echo "$r"; cat >/dev/null; done
  #     -> a            (b and c eaten by the child)
  #   ...with `cat >/dev/null </dev/null`  -> a, b, c
  # A stub CLI cannot catch this, because a stub does not read stdin.
  if [[ -n "$TIMEOUT_BIN" ]]; then
    ( cd "$celldir" && "$TIMEOUT_BIN" "${timeout_s}" "${argv[@]}" ) \
        >"$stdout_file" 2>"$OUT/cells/${label}.stderr" </dev/null
  else
    ( cd "$celldir" && "${argv[@]}" ) \
        >"$stdout_file" 2>"$OUT/cells/${label}.stderr" </dev/null
  fi
  rc=$?
  stop="$(date +%s)"
  rm -rf "$celldir"

  ARGV_JOINED="$(printf '%s\x1f' "${argv[@]}")" \
  LABEL="$label" CID="$cid" MODEL="$model" SID="$sid" NREP="$n" \
  RC="$rc" EXPECT="$expect" DUR="$((stop-start))" \
  STDOUT_FILE="$stdout_file" EXPECTED_TOOLS="$expected_tools" \
  python3 - "$cell_json" <<'CELLPY'
import hashlib, json, os, re, sys

out = os.environ["STDOUT_FILE"]
raw = open(out, "rb").read() if os.path.exists(out) else b""
text = raw.decode("utf-8", "replace")
rc = int(os.environ["RC"])
expect = int(os.environ["EXPECT"])
expected_tools = [t for t in os.environ["EXPECTED_TOOLS"].split(",") if t]

# Which tools did the cell actually reach? Best-effort extraction from the
# event stream; an unparseable stream is itself a reason to call the cell
# unmeasured rather than to guess.
tools = sorted(set(re.findall(r'"name"\s*:\s*"([A-Za-z_][A-Za-z0-9_]*)"', text)))
tools = [t for t in tools if t and t[0].isupper()]

reason = None
if rc == 124:
    reason = "timeout"
elif not raw.strip():
    reason = "empty stdout -- the run never produced anything"
elif len(raw) < 200:
    reason = "stdout under 200 bytes -- too short to be a real reply"
elif re.search(r"(?i)(failed to authenticate|oauth session expired|usage limit|not logged in)", text):
    reason = "CLI refusal banner -- the run never happened"
else:
    stray = [t for t in tools if t not in expected_tools]
    if expected_tools and stray:
        # Denying is best-effort; THIS is the gate. A cell that reached
        # outside the expected surface was never fairly measured -- it is not
        # a FAIL, because nothing about the work was actually tested.
        reason = "reached tools outside expected_tools: %s" % ", ".join(stray)

outcome = "UNMEASURED" if reason else ("PASS" if rc == expect else "FAIL")

json.dump({
    "label": os.environ["LABEL"],
    "case": os.environ["CID"],
    "model": os.environ["MODEL"],
    "plugin_state": os.environ["SID"],
    "repeat": int(os.environ["NREP"]),
    "argv": [a for a in os.environ["ARGV_JOINED"].split("\x1f") if a],
    "exit": rc,
    "expect_exit": expect,
    "duration_s": int(os.environ["DUR"]),
    "stdout_sha256": hashlib.sha256(raw).hexdigest(),
    "stdout_bytes": len(raw),
    "tools_used": tools,
    "outcome": outcome,
    "unmeasured_reason": reason,
}, open(sys.argv[1], "w"), indent=2)
print("  %-38s %-12s exit=%-3s %ss" % (os.environ["LABEL"], outcome, rc, os.environ["DUR"]))
CELLPY
done < <(python3 -c "$VALIDATE_PY" "$MATRIX" cells)

[[ "$DRY_RUN" -eq 1 ]] && exit 0

OUT="$OUT" python3 - <<'SUMPY'
import collections, json, os, pathlib

out = pathlib.Path(os.environ["OUT"])
cells = [json.loads(p.read_text()) for p in sorted((out / "cells").glob("*.json"))]

by_combo = collections.defaultdict(list)
for c in cells:
    by_combo[(c["case"], c["model"], c["plugin_state"])].append(c)

rows, tally = [], collections.Counter()
for combo, group in sorted(by_combo.items()):
    measured = [g for g in group if g["outcome"] != "UNMEASURED"]
    # UNMEASURED is excluded from the denominator, never counted as a failure.
    # Three independent derivations in this codebase say so; this is the third.
    if not measured:
        outcome = "UNMEASURED"
    elif len({g["outcome"] for g in measured}) > 1 or len({g["stdout_sha256"] for g in measured}) > 1:
        outcome = "UNSTABLE" if len({g["outcome"] for g in measured}) > 1 else measured[0]["outcome"]
    else:
        outcome = measured[0]["outcome"]
    tally[outcome] += 1
    rows.append({
        "case": combo[0], "model": combo[1], "plugin_state": combo[2],
        "outcome": outcome,
        "measured": len(measured), "total": len(group),
        "distinct_stdout": len({g["stdout_sha256"] for g in measured}),
    })

summary = {"cells": len(cells), "combinations": len(rows), "tally": dict(tally), "rows": rows}
(out / "summary.json").write_text(json.dumps(summary, indent=2))

print()
print("%-16s %-10s %-10s %-12s %-9s %s" % ("case", "model", "arm", "outcome", "measured", "distinct stdout"))
print("-" * 78)
for r in rows:
    print("%-16s %-10s %-10s %-12s %-9s %s" % (
        r["case"], r["model"], r["plugin_state"], r["outcome"],
        "%d/%d" % (r["measured"], r["total"]), r["distinct_stdout"]))
print()
print("tally:", ", ".join("%s=%d" % kv for kv in sorted(tally.items())) or "nothing ran")
if tally.get("UNMEASURED"):
    print()
    print("UNMEASURED combinations have NO rate, only missing data. They are excluded")
    print("from every denominator and are never a reason to re-dispatch: fix the")
    print("environment, then re-run. Re-running against a broken environment measures")
    print("the weather.")
print("summary: %s/summary.json" % out)
SUMPY
