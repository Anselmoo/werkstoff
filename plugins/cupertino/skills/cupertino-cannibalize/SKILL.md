---
name: cupertino-cannibalize
description: "USER-INVOKED ONLY — never automatic, never run as part of cupertino-review's pipeline or any other automatic stage. Use only when the user explicitly asks, on a deliberate post-ship cadence, whether to replace a currently-successful, load-bearing thing with a better successor built in-house — the iPhone-cannibalizing-the-iPod move. Trigger only on explicit requests like 'should we cannibalize X', 'is it time to replace our own best thing', or a direct ask to run this specific technique by name."
---

This technique only runs when the user explicitly asks for it by name or clear equivalent. A PreToolUse hook denies dispatching this skill while a `cupertino-review` pipeline is active in this repo (`.cupertino/flags/review-pipeline-active`) — if you see that denial, finish or exit the review pipeline first, then invoke this skill separately and explicitly. Do not try to route around the hook; if `cupertino-review` surfaces a cannibalization question organically, it will flag it and suggest exactly this: come back and invoke this skill on its own.

## Steps

1. **Name the current most-successful, load-bearing thing** under consideration — precisely, so it's clear what would actually be replaced and what depends on it today.
2. **Apply the exact distinguishing test**: *could this keep improving incrementally?*
   - If **no** — it is a **Vista Trap**: the current thing is failing not because someone chose to replace it, but because its architecture has run out of runway. This is bad, and the fix is `cupertino-longevity`'s Rosetta Roadmap, not cannibalization. Say so and redirect rather than dressing up a forced rewrite as a bold strategic move.
   - If **yes** — it is a genuine **cannibalization candidate**: the current thing is fine and could keep improving, but a deliberately-built successor could be meaningfully better. This is the iPhone-vs-iPod case: healthy, chosen, not forced.
3. **For a genuine candidate only**: assess the competitive threat or opportunity driving this — what happens if you don't build the successor yourselves (a competitor does it, the market moves past the current thing, or nothing happens and it's actually not worth doing yet).
4. **Explicit build-it-ourselves decision**: state plainly whether to proceed, and if so, roughly what the successor needs to do better than the incumbent to justify eating your own product.

## Output format

Named thing → distinguishing-test verdict (with the reasoning, not just the label) → if Vista Trap, the redirect to `cupertino-longevity`; if genuine candidate, the competitive assessment and the explicit decision.
