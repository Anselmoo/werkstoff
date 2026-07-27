---
name: cupertino-reveal
description: "Use at ship-time, as the last automatic step for a finished feature, module, tool, or API, to deliver exactly one non-obvious, high-leverage addition in a keynote 'and one more thing' structure. Trigger on 'what's missing here', 'is there anything else this needs before shipping', or automatically as the final stage when cupertino-review runs the full pipeline. Never produces a list — exactly one suggestion, and it must be built, not pitched."
---

Deliver exactly one reveal. Never a numbered list, never a set of alternatives to choose from — the discipline of "and one more thing" is that there is exactly one thing.

## Steps

1. **State plainly what the shipped artifact does** — the baseline, so the gap is legible against it.
2. **Name the gap**: the specific capability or delight that's genuinely missing, that a user would eventually ask for or silently miss without knowing to ask.
3. **"And one more thing"** — the pivot. Name the one idea.
4. **Describe it**: what it is, concretely.
5. **Explain why it wasn't already there** — a real reason (it required the foundation just built, it wasn't obvious until this artifact existed, it's a genuine insight rather than a known backlog item).
6. **Implementation sketch**, then **build it** — production-grade, matched to the artifact's actual stack. A reveal that stays pitched as a roadmap item is not a reveal; "real artists ship."
7. **Impact sentence**: one sentence on what this actually changes for the person using the artifact.

## Validate mechanically

Do not eyeball the "exactly one, and it's built" requirements:

```bash
echo '{"text": "<your full reveal writeup, including the code block>"}' | python3 "${CLAUDE_PLUGIN_ROOT}/scripts/validators.py" reveal-shape
```

This rejects the reveal if it contains a numbered or bulleted list of suggestions (more than one idea presented), or if it has no fenced code block at all (meaning nothing was actually built). If it fails, cut to one idea and build it before presenting again.

## Refuse

- Never suggest something already obviously on the user's mental backlog — the reveal must be genuinely surprising.
- Never suggest something trivial ("add type hints", "fix a typo") — it must be non-trivial and high-leverage.
- Never present it as a future consideration rather than working code.
