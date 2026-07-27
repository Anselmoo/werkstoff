---
name: cupertino-focus
description: "Use immediately after cupertino-backwards has established the customer experience, to reduce a sprawling portfolio of shipped and planned products, feature lines, modes, or variants down to the smallest focused set before architecture work commits effort. Trigger on requests like 'we have too many modes/plans/tiers/variants', 'help us decide what to cut', or any planning conversation where the honest list of things-in-flight is longer than anyone wants to admit."
---

Reduce first. Architecture should never be built to support a portfolio that has not yet been cut down.

This skill is gated: a PreToolUse hook blocks it until `cupertino-backwards` has run in this repo (it checks for `.cupertino/flags/backwards-done`). If you see a denial for that reason, run `cupertino-backwards` first — do not work around the gate.

## Steps

1. **Enumerate the full portfolio**: every shipped and planned product, feature line, mode, and variant, without editorializing yet.
2. **Build a grid**: pick the 2 (or 3) structural axes that actually matter for this portfolio — not generic axes, the ones where item placement reveals real overlap or gaps. Place every enumerated item on the grid.
3. **Cut list**: sort every item into killed, merged, or surviving. For every item you cut or merge, state the cost explicitly — what capability, audience, or revenue is actually lost, not just what is gained by focusing. A cut with no acknowledged cost is a cut nobody has actually thought through.
4. **One-sentence test for survivors**: every surviving product or feature line must be describable in exactly one sentence.

## Validate mechanically

Do not eyeball the one-sentence rule. For each survivor, run:

```bash
echo '{"survivors": [{"name": "...", "description": "..."}, ...]}' | python3 "${CLAUDE_PLUGIN_ROOT}/scripts/validators.py" one-sentence-per-survivor
```

Any survivor the checker flags needs a deeper cut, not a longer sentence — if a survivor still needs a paragraph of caveats to describe, it is actually two things wearing one name, or it has not been reduced enough. Go back to the cut list, not the prose.

## Output format

Present, in order: the full enumerated portfolio, the grid with every item placed, the cut list with losses named, and the validated one-sentence survivor descriptions. If the validator flags any survivor, show the revised cut that resolved it — don't just report the failure and stop.
