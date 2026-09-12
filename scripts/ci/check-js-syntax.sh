#!/usr/bin/env bash
#
# Three assertions over plugins/*/workflows/*.js, in increasing strength.
#
#   1. it parses            -- node --check
#   2. it is SHAPED like a workflow script -- it has a top-level `return`
#   3. it is clean under the pinned biome rule set -- biome.jsonc
#
# (1) was the whole of this script for its first year. It proves a file
# parses and nothing more.
#
# WHY (2) EXISTS, AND WHY THE SIGNAL LOOKS BACKWARDS: a Workflow script is not
# a module. The runtime evaluates its BODY in an async context, so `args` is an
# injected global and a top-level `return` is the result -- that is the whole
# calling convention. biome parses .js as an ES module, where a top-level
# `return` is illegal, so it emits exactly one message on every correctly
# shaped file:
#
#     Illegal return statement outside of a function
#
# node --check does not, because Node wraps CommonJS in a function where
# top-level return is legal. Neither checker models the runtime, and they
# disagree about all fifteen files.
#
# So this script INVERTS that diagnostic: the message is REQUIRED, and a file
# that does not produce it has no top-level return and returns undefined at
# run time. That is not hypothetical. plugins/arbeitsplan/workflows/run.js
# shipped wrapped in `export default async function run(rawArgs)`, the only
# file in the repo in that shape. It parsed under node --check, it was the one
# file biome parsed CLEANLY, and every agent dispatch in it was unreachable --
# the body defined a function nothing called and fell off the end. Wiring
# biome without this inversion would have failed the fourteen correct files
# and passed the broken one.
#
# Coupling to biome's wording is deliberate and is the reason BIOME_VERSION is
# pinned. If a future biome rephrases the message, --selftest's KNOWN-GOOD
# case goes red immediately and loudly, rather than this check quietly
# asserting nothing -- which is the failure direction CLAUDE.md's defect table
# is entirely about.
#
# Escape hatch: ALLOW_MISSING_BIOME=1 downgrades (3) and (2) to a loud SKIP
# when biome cannot be obtained. Default is to FAIL, because a check that
# silently skips reports success every run and nobody looks again.
set -euo pipefail

BIOME_VERSION="2.5.10"
EXPECTED_PARSE_MESSAGE="Illegal return statement outside of a function"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# --- biome resolution ---------------------------------------------------------
# Pinned, never "whatever is installed": ruff.toml records what an unpinned
# linter cost here (0 findings under 0.15.22, 325 under 0.16.6, same commit).
resolve_biome() {
  if [ -n "${BIOME_BIN:-}" ]; then
    printf '%s\n' "$BIOME_BIN"
    return 0
  fi
  if command -v npx >/dev/null 2>&1; then
    printf '%s\n' "npx --yes @biomejs/biome@${BIOME_VERSION}"
    return 0
  fi
  return 1
}

# --- (1) node --check ---------------------------------------------------------
run_node_check() {
  local root="$1" fail=0 count=0 file
  while IFS= read -r -d '' file; do
    count=$((count + 1))
    # `< /dev/null` because a child that reads stdin eats the rest of this
    # loop's input; that exact bug silently halved a sweep in run_matrix.sh.
    if ! node --check "$file" </dev/null 2>&1; then
      echo "FAIL(parse): $file"
      fail=1
    fi
  done < <(cd "$root" && find plugins -path '*/workflows/*.js' -print0 | sort -z)
  if [ "$fail" -eq 0 ]; then
    echo "  node --check: all $count workflow .js file(s) parse cleanly."
  fi
  return "$fail"
}

# --- (2) + (3) biome ----------------------------------------------------------
run_biome_check() {
  local root="$1" biome_cmd="$2" raw rc=0
  raw="$(mktemp)"
  # biome exits non-zero whenever it emits a diagnostic, which is the normal
  # case here -- the 23 expected parse messages. Judge from the JSON, not from
  # the exit code, but refuse to treat unparseable output as a pass.
  (cd "$root" && eval "$biome_cmd" lint --reporter=json plugins/*/workflows/*.js) >"$raw" 2>/dev/null </dev/null || true

  EXPECTED_PARSE_MESSAGE="$EXPECTED_PARSE_MESSAGE" python3 - "$root" "$raw" <<'PYEOF'
import glob
import json
import os
import sys
from pathlib import Path

root, raw = sys.argv[1], sys.argv[2]
expected = os.environ["EXPECTED_PARSE_MESSAGE"]

text = Path(raw).read_text()
try:
    report = json.loads(text)
except json.JSONDecodeError:
    # An unmeasured run is never a pass. This repo has derived that rule three
    # separate times (run.sh's ERROR, decode.js's readable:false,
    # run_trigger_evals.py's INDETERMINATE); it applies to the instrument too.
    sys.stderr.write(
        "ERROR: biome produced no parseable JSON -- the check did not run, so it "
        "cannot report a pass.\n"
        f"First 400 bytes of what it wrote:\n{text[:400]}\n"
    )
    raise SystemExit(2)

files = sorted(glob.glob(str(Path(root) / "plugins/*/workflows/*.js")))
rel = [str(Path(f).relative_to(root)) for f in files]
if not rel:
    sys.stderr.write("ERROR: no workflow scripts found; refusing to report a pass.\n")
    raise SystemExit(2)


def path_of(diag):
    loc = diag.get("location", {}).get("path")
    return loc.get("file") if isinstance(loc, dict) else loc


diagnostics = report.get("diagnostics", [])
shaped = {f: 0 for f in rel}
failures = []

for diag in diagnostics:
    where, category = path_of(diag), diag.get("category")
    if category == "parse":
        if diag.get("message") == expected:
            if where in shaped:
                shaped[where] += 1
        else:
            failures.append(f"FAIL(parse): {where}: {diag.get('message')}")
    else:
        line = diag.get("location", {}).get("start", {}).get("line", "?")
        failures.append(f"FAIL(lint): {where}:{line} {category}: {diag.get('message')}")

for f in rel:
    if shaped[f] == 0:
        failures.append(
            f"FAIL(shape): {f}: no top-level `return`. A Workflow script's body IS "
            "the function -- `args` is an injected global and the top-level "
            "`return` is the result. A file with no top-level return dispatches "
            "nothing and resolves to undefined. Do not wrap the body in "
            "`export default`."
        )

if failures:
    for line in failures:
        print(line)
    raise SystemExit(1)

print(f"  biome({len(rel)} files): 0 lint findings under the pinned rule set.")
print(f"  shape: all {len(rel)} file(s) carry a top-level return.")
PYEOF
  rc=$?
  rm -f "$raw"
  return "$rc"
}

# --- selftest -----------------------------------------------------------------
# Every assertion above is planted-defect tested. A guard that cannot fail
# reports success every run and nobody looks again.
selftest() {
  local biome_cmd box pass=0 fail=0
  if ! biome_cmd="$(resolve_biome)"; then
    echo "SELFTEST: cannot resolve biome; nothing to calibrate." >&2
    return 1
  fi
  box="$(mktemp -d)"
  trap 'rm -rf "$box"' RETURN

  _case() { # name, expected_rc, file body, [biome command override]
    local name="$1" want="$2" body="$3" cmd="${4:-$biome_cmd}" got=0
    rm -rf "$box/plugins"
    mkdir -p "$box/plugins/probe/workflows"
    printf '%s\n' "$body" >"$box/plugins/probe/workflows/p.js"
    cp "$REPO_ROOT/biome.jsonc" "$box/biome.jsonc"
    run_biome_check "$box" "$cmd" >/dev/null 2>&1 || got=$?
    if [ "$got" -eq "$want" ]; then
      echo "  ok   $name (rc=$got)"
      pass=$((pass + 1))
    else
      echo "  FAIL $name: expected rc=$want, got rc=$got"
      fail=$((fail + 1))
    fi
  }

  echo "check-js-syntax --selftest"
  # KNOWN-GOOD. Also the canary for biome rephrasing the parse message: if the
  # wording changes, this case flips to rc=1 and says so.
  _case "known-good workflow shape passes" 0 \
    'export const meta = { name: "p", description: "d" }
const v = (args && args.v) || 1
log(`v=${v}`)
return { v }'

  # (2) the inversion -- the exact shape arbeitsplan/run.js shipped in.
  _case "export default wrapper is rejected (no top-level return)" 1 \
    'export const meta = { name: "p", description: "d" }
export default async function run(a) {
  return { v: a }
}'

  # (3) a live rule, and the globals list that makes it usable.
  _case "typo-d runtime hook is rejected" 1 \
    'export const meta = { name: "p", description: "d" }
const r = agnet("go")
return { r }'
  _case "correctly spelled runtime hook passes" 0 \
    'export const meta = { name: "p", description: "d" }
const r = await agent("go")
return { r }'

  # a real silent-failure shape, not a style preference
  _case "duplicate object key is rejected" 1 \
    'export const meta = { name: "p", description: "d" }
const schema = { type: "object", type: "array" }
return { schema }'

  # A genuine syntax error must still fail. Note WHY it fails: biome bails
  # before it ever sees a top-level return, so this case is caught by the
  # SHAPE assertion, not by the parse-message branch. Recorded because a
  # sabotage run proved it -- blanking the parse-message branch leaves this
  # case green, so on its own it does not calibrate that branch at all.
  _case "genuine syntax error is rejected (via the shape assertion)" 1 \
    'export const meta = { name: "p", description: "d" }
const broken = (
return { broken }'

  # The case that actually calibrates the parse-message branch: a valid
  # top-level return (so the shape assertion is SATISFIED and cannot cover for
  # anything) plus a second, different parse error. `await` in a non-async
  # helper is the realistic form -- it parses under node --check's CommonJS
  # wrapper and throws only when that helper is called.
  _case "await in a non-async helper is rejected" 1 \
    'export const meta = { name: "p", description: "d" }
function f() { return await agent("x") }
return { f }'

  # The instrument must fail loudly when it did not RUN. Everything above
  # calibrates what biome reports; this calibrates the case where biome
  # reports nothing usable -- npx with no network, a malformed biome.jsonc, an
  # OOM kill. rc=2 is deliberately distinct from rc=1: one says the files are
  # bad, the other says nothing is known about them, and collapsing the two is
  # how an outage gets recorded as a pass.
  local stub="$box/stub-nonjson.sh"
  printf '%s\n' '#!/usr/bin/env bash' \
    'echo "biome: error: configuration could not be loaded" >&2' \
    'echo "<not json>"' >"$stub"
  chmod +x "$stub"
  _case "non-JSON from biome is an error, not a pass" 2 \
    'export const meta = { name: "p", description: "d" }
return { ok: true }' \
    "$stub"

  echo "selftest: $pass passed, $fail failed"
  [ "$fail" -eq 0 ]
}

# --- main ---------------------------------------------------------------------
if [ "${1:-}" = "--selftest" ]; then
  selftest
  exit $?
fi

status=0
echo "check-js-syntax: plugins/*/workflows/*.js"
run_node_check "$REPO_ROOT" || status=1

if biome_cmd="$(resolve_biome)"; then
  run_biome_check "$REPO_ROOT" "$biome_cmd" || status=1
else
  if [ "${ALLOW_MISSING_BIOME:-}" = "1" ]; then
    echo "  SKIP: biome unavailable (no npx, no BIOME_BIN). Shape and lint checks did NOT run." >&2
  else
    echo "  FAIL: biome unavailable (no npx, no BIOME_BIN), so the shape and lint" >&2
    echo "        checks could not run. Set ALLOW_MISSING_BIOME=1 to downgrade this" >&2
    echo "        to a skip; node --check alone only proves the files parse." >&2
    status=1
  fi
fi

exit "$status"
