---
name: compass-ground-evidence
description: >-
  Checks that every factual claim in an answer or artifact is traceable to a
  specific source — a file:line, a URL, or explicitly-flagged prior knowledge —
  and refuses to assert anything beyond what's actually verified. Use whenever an
  answer, summary, or report makes assertions that need grounding rather than
  recall: "cite your sources", "don't make this up", "ground this in the actual
  transcript/code/docs/data", a number or metric that must trace back to where it
  came from, "verify before asserting", or a factual-claim-heavy stage of
  compass-solve.
---

# compass-ground-evidence

List claims first, cite each inline, refuse the unsupported ones with the exact
template — then **validate with the guard**.

`GUARD="python3 ${CLAUDE_PLUGIN_ROOT}/scripts/compass.py"`

## Process

1. **List the discrete factual claims before drafting the answer.**
2. For each claim assign a `status`:
   - `verified` — checked this session against a real source; cite it inline.
   - `warned` — from training/general knowledge, not checked this session; mark it
     `(Prior knowledge ⚠️)`.
   - `refused` — the sources do not support it.
3. **Cite every non-refused claim inline at the point it's made**, as `(file:line)`,
   `(URL)`, or `(Prior knowledge ⚠️)`.
4. **Refuse any unsupported claim with the EXACT template:**
   `The available [sources] do not contain sufficient information to [claim].`
5. **MUST NOT combine two partial sources into one claim without explaining the
   inference** that joins them.

## Validate

```
echo '{"claims":[
  {"status":"verified","text":"retries default to 3","citation":"(config.py:88)"},
  {"status":"warned","text":"exponential backoff is common","citation":"(Prior knowledge ⚠️)"},
  {"status":"refused","text":"The available logs do not contain sufficient information to identify the failing host."}
]}' | $GUARD ground -
```

The guard rejects any non-refused claim without an inline citation, and any
refused claim not using the exact template. It returns the **coverage line**
(total, Verified, ⚠️, refused). A non-zero exit means a claim was ungrounded —
cite it, flag it, or refuse it properly.

## Output
- the answer, using only Verified sources and explicitly-⚠️ facts
- every claim cited inline
- the coverage line
