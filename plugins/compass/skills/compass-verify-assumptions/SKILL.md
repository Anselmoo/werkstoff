---
name: compass-verify-assumptions
description: >-
  Checks exactly ONE named assumption against real evidence in at most 3 steps and
  reports one outcome: confidence raised (>=90), reading changed, or still
  unresolved. Use to resolve a single load-bearing uncertainty — typically a
  blocking entry surfaced by compass-clarify-scope: "verify this one assumption",
  "is it actually true that X", "check this before we rely on it". For multiple
  uncertainties, invoke once per uncertainty — the step budget is never shared.
---

# compass-verify-assumptions

Resolve **one** assumption in a bounded loop, then **validate with the guard**. The
step cap, the one-per-invocation rule, and the confidence gate are enforced in
code.

`GUARD="python3 ${CLAUDE_PLUGIN_ROOT}/scripts/compass.py"`

## Input
One uncertainty entry: `{element, default_interpretation, confidence,
other_readings, blocking}`.

## Rules

- **Resolve exactly one assumption per invocation.** For multiple uncertainties,
  invoke this skill once each — **never share the 3-step budget across entries.**
- Run a **Reasoning / Action / Observation** loop, **at most 3 steps total** (hard
  cap). Each action closes a named gap.
- **Stop as soon as any outcome is reached**, even if steps remain in the budget.
- Report **exactly one outcome**:
  - `confidence_raised` — new confidence **must be >= 90**; **cite the source(s)**
    (file:line or URL).
  - `reading_changed` — the default interpretation was wrong; state the new one and
    **cite the source(s)**.
  - `still_unresolved` — use the refusal template from `compass-ground-evidence`
    (`The available [sources] do not contain sufficient information to …`).

## Validate

```
echo '{
  "assumption":"target env is prod",
  "steps":[
    {"reasoning":"need to know which env the config targets","action":"read config","observation":"env=production"}
  ],
  "outcome":{"kind":"confidence_raised","confidence":95,"citations":["(config.yaml:3)"]}
}' | $GUARD verify -
```

The guard refuses: more than 3 steps, a list of assumptions, a `confidence_raised`
below 90, or a resolved outcome with no citation. A non-zero exit means an outcome
was accepted that shouldn't be — keep it `still_unresolved`.

## Output
- one outcome: confidence raised (>=90), reading changed, or still_unresolved
