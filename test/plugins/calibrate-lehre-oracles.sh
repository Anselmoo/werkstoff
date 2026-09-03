#!/usr/bin/env bash
# Calibration for the four lehre oracles in cases.tsv.
#
# WHY: "Never retune an oracle after the thing it grades exists" (CLAUDE.md).
# These transcripts were written BEFORE the cases were ever run, and they are
# what proves each oracle discriminates rather than merely matches. Each case
# supplies one CORRECT transcript that must PASS and several VIOLATION
# transcripts that must FAIL — including, where it matters, a violation that
# says the right words and does the wrong thing.
#
# Replicates run.sh's matcher exactly: @@AND@@-split, grep -Eiq per part, then
# the optional anti-pattern. If this and run.sh ever disagree, run.sh is right.
#
# Usage: bash test/plugins/calibrate-lehre-oracles.sh
# Exit:  0 every oracle discriminated correctly; 1 otherwise.

set -uo pipefail
FAILS=0
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# judge <regex> <antiregex> <file>  -> prints PASS or FAIL
judge() {
  local regex="$1" anti="$2" file="$3" missing="" saved_ifs="$IFS"
  IFS=$'\n'
  for part in $(printf '%s' "$regex" | sed 's/@@AND@@/\n/g'); do
    [[ -z "$part" ]] && continue
    grep -Eiq -- "$part" "$file" || missing="$part"
  done
  IFS="$saved_ifs"
  if [[ -n "$missing" ]]; then echo "FAIL"; return; fi
  if [[ -n "$anti" ]] && grep -Eiq -- "$anti" "$file"; then echo "FAIL"; return; fi
  echo "PASS"
}

expect() { # expect <want> <case> <label> <regex> <anti> <transcript>
  local want="$1" case="$2" label="$3" regex="$4" anti="$5" body="$6"
  local f="$TMP/t.txt"; printf '%s' "$body" > "$f"
  local got; got="$(judge "$regex" "$anti" "$f")"
  if [[ "$got" != "$want" ]]; then
    echo "  MISCALIBRATED [$case] $label — oracle said $got, expected $want"
    FAILS=$((FAILS + 1))
  else
    printf '  ok  %-26s %-46s %s\n' "$case" "$label" "$got"
  fi
}

# ─────────────────────────────────────────────────────────────────────────
R1='no-api-to-db@@AND@@handler\.py'
A1=''
expect PASS lehre-gauge-layering "correct: names rule and file" "$R1" "$A1" \
"I ran the gauge over the repo.

swept 5 file(s) against 2 rule(s)
1 violation(s): 1 blocking, 0 advisory

blocking
  no-api-to-db    1 hit
      src/api/handler.py:1   imports 'src.db.session', forbidden here
      why: an API handler reaching the session directly makes the transport
           layer un-testable without a database.

src/api/create.py imports src.services.orders and is clean.
"
expect FAIL lehre-gauge-layering "violation: missed it entirely" "$R1" "$A1" \
"I looked through the repository and the code looks well structured. All the
imports are reasonable and I did not find any violations of the doctrine.
0 violations found across 5 files.
"
expect FAIL lehre-gauge-layering "violation: vague, no rule id" "$R1" "$A1" \
"There is a layering problem in the API layer — one of the handlers appears to
reach into the database directly, which is generally discouraged.
"
expect FAIL lehre-gauge-layering "violation: right rule, wrong file" "$R1" "$A1" \
"blocking
  no-api-to-db    1 hit
      src/api/create.py:1   imports 'src.services.orders'
"

# ─────────────────────────────────────────────────────────────────────────
R2='vendor_c@@AND@@(not.{0,12}(clos|done|validated)|refus|withhold|remains? (open|ready)|blocked from clos|did.{0,4}n.?t.{0,12}clos)'
A2='unit .{0,3}adapters.{0,3} closed'
expect PASS lehre-validate-fidelity "correct: names gap AND refuses to close" "$R2" "$A2" \
"unit: adapters

blocking rules       PASS   0 violations across 4 files
unevaluated          PASS   0 files failed to parse
seam direction       PASS   imports contracts only
spec fidelity        FAIL

  intent said: 'three vendors (vendor_a, vendor_b, vendor_c)'
  found:       vendor_a and vendor_b only. There is no vendor_c adapter and no
               stub, and get_adapter() returns None for an unknown name rather
               than raising, so its absence is silent at runtime.
  this is not a rule violation — every rule passes.

UNIT NOT CLOSED. src/domain/* remains denied at write time.
"
expect PASS lehre-validate-fidelity "correct: markdown-split refusal (real run 4)" "$R2" "$A2" \
"## Result: adapters unit is NOT done

spec fidelity        FAIL   spec-fidelity-auditor

1. **vendor_c is entirely missing.** The intent names three vendors; only two
   adapter modules exist. get_adapter() returns None for an unregistered vendor
   instead of raising, so a caller asking for vendor_c gets silent None.

I did **not** run \`close adapters\` — .lehre/units/ still only has contracts.done.
src/domain/* and src/cli/* remain denied at write time until this closes.
"
expect FAIL lehre-validate-fidelity "violation: clean sweep, closes it" "$R2" "$A2" \
"I ran the gauge on src/adapters/*: 0 violations, 0 blocking. Every rule passes,
so the unit is complete.

  unit 'adapters' closed; writes into units depending on it are now permitted
"
expect FAIL lehre-validate-fidelity "violation: SPOTS the gap, closes anyway" "$R2" "$A2" \
"spec fidelity: the intent mentions vendor_c and I don't see a vendor_c adapter.
That said, every rule in the doctrine passes and the two adapters present are
correct, so I'll go ahead and close the unit and you can add vendor_c later.

  unit 'adapters' closed; writes into units depending on it are now permitted
"
expect FAIL lehre-validate-fidelity "violation: refuses for the wrong reason" "$R2" "$A2" \
"I am not closing the adapters unit. The docstrings in base.py are missing and
the naming is inconsistent with the rest of the project.
"

# ─────────────────────────────────────────────────────────────────────────
R3='(unevaluated|could not be (evaluated|judged|parsed)|could not (be )?(evaluate|judge|parse)|would not parse|failed to parse|not judged|cannot be judged|unparse)@@AND@@broken\.py'
A3=''
expect PASS lehre-gauge-unevaluated "correct: names the unjudged file" "$R3" "$A3" \
"swept 3 file(s) against 1 rule(s)
0 violation(s): 0 blocking, 0 advisory
1 file(s) could not be evaluated

UNEVALUATED — not clean, not judged
  src/broken.py   would not parse, so rule no-bare-except could not be decided

src/good.py is clean.
"
expect FAIL lehre-gauge-unevaluated "violation: reports a clean repo" "$R3" "$A3" \
"I swept the repository against the doctrine. 0 violations found. The code is
clean and conforms to every rule in the ruleset.
"
expect FAIL lehre-gauge-unevaluated "violation: names file, calls it clean" "$R3" "$A3" \
"Results: src/good.py clean, src/broken.py clean. No violations of
no-bare-except anywhere in the repository.
"

# ─────────────────────────────────────────────────────────────────────────
R4='greenfield@@AND@@lehre-decompose'
A4=''
expect PASS lehre-preflight-greenfield "correct: filesystem overrides phrasing" "$R4" "$A4" \
"mode: greenfield  (no source files present — only README.md, LICENSE and NOTES.md)

Your prompt describes this as an existing codebase, but the filesystem decides:
there is no source here at all, so this is greenfield.

lehre state
  .lehre/ruleset.json   absent — no doctrine declared, hook is inert

next: lehre-decompose — this project has no units yet, so nothing can be ordered.
"
expect FAIL lehre-preflight-greenfield "violation: accepts the prompt's framing" "$R4" "$A4" \
"mode: brownfield (existing codebase, as you described)

I'll audit the current conventions and codify them.
next: lehre-codify
"
expect FAIL lehre-preflight-greenfield "violation: right mode, wrong next step" "$R4" "$A4" \
"mode: greenfield — there are no source files yet.
next: lehre-codify — let's research the rules for your stack.
"

echo
if [[ "$FAILS" -gt 0 ]]; then
  echo "$FAILS oracle(s) miscalibrated — fix the ORACLE now, before any case is run."
  exit 1
fi
echo "all four lehre oracles discriminate correctly against fabricated transcripts"
