---
name: compass-clarify-scope
description: >-
  Scopes an ambiguous task before any work begins — restates it with defaults
  made explicit, lists known facts (flagging low-confidence ones), and surfaces
  the interpretation forks that could send the work the wrong way. Use when a
  task's phrasing supports multiple reasonable interpretations, success criteria
  aren't stated, or scope is underspecified: "what exactly do you want here",
  "before I start, let me pin this down", a vague one-line request, or the first
  phase of compass-solve.
---

# compass-clarify-scope

Produce four structured outputs, then **validate them with the guard**. The guard
enforces the confidence gates in code — a missing `confidence` or `blocking` field
is rejected, never defaulted.

`GUARD="python3 ${CLAUDE_PLUGIN_ROOT}/scripts/compass.py"`

## Outputs

1. **scoped_task** — one clear restatement with every default interpretation
   stated inline (e.g. "…assuming *production* config, since none was named").
2. **known_facts** — a numbered list. Each fact carries a `confidence` (0-100).
   The guard marks any fact **below 90** with ⚠️.
3. **flagged_uncertainties** — for each interpretation fork:
   `{element, default_interpretation, confidence, other_readings, blocking}`.
   `confidence` and `blocking` are load-bearing and mandatory.
4. **success_criteria** — list of `{criterion, status}`.

## The rules (enforced in code)

- **Any uncertainty with confidence below 70 MUST be flagged.** The guard's
  `clarify` check computes `flagged` per entry — you do not eyeball it.
- **Any known fact below 90% confidence MUST be marked ⚠️.**
- **MUST NOT silently adopt a default interpretation for a flagged item.** Present
  it.
- **MUST pause and wait for user input if any flagged uncertainty is load-bearing**
  (`blocking: true`) for the deliverable. The guard returns `must_pause`.

## Validate

```
echo '{
  "flagged_uncertainties":[{"element":"target env","default_interpretation":"prod","confidence":55,"blocking":true,"other_readings":["staging"]}],
  "known_facts":[{"fact":"repo uses pnpm","confidence":95},{"fact":"CI is GH Actions","confidence":70}]
}' | $GUARD clarify -
```

The result gives `flagged_count`, `blocking_uncertainties`, and `must_pause`. **If
`must_pause` is true, stop and ask the user** — do not proceed under a guess. A
non-zero exit means a gating field was missing; supply it, never invent it.
