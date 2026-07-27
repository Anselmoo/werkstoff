---
name: cupertino-review
description: "Use when a project spans multiple lifecycle moments and the user wants the whole cupertino discipline applied end-to-end in one pass — 'give this the full cupertino treatment', 'review this like Apple would', 'run the whole design lifecycle on this'. Composes the plugin's other techniques as fixed, sequenced stages rather than requiring the user to invoke each one by hand. Not for a single lifecycle moment with one obvious technique — use that technique directly instead."
---

Run the fixed pipeline, in order, on the given project or scope:

```
cupertino-backwards -> cupertino-focus -> [cupertino-longevity & cupertino-integrate, side by side]
  -> cupertino-council -> cupertino-prototype -> cupertino-elevate -> cupertino-unbox -> cupertino-reveal
```

## Before you start

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/state.py" init
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/state.py" set review-pipeline-active
```

Setting this flag is what makes the PreToolUse hook refuse an automatic dispatch of `cupertino-cannibalize` for the duration of this pipeline — that refusal is intentional, not a bug to route around. Clear the flag when you finish (success, early stop, or the user cancels):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/state.py" clear review-pipeline-active
```

## Sequence

1. **cupertino-backwards** — invoke it for real; do not skip straight to focus. It writes the `backwards-done` marker other stages are gated on.
2. **cupertino-focus** — reduce the portfolio implied by this scope.
3. **cupertino-longevity and cupertino-integrate together** — invoke both on the architecture decisions this scope raises. **Present both readouts side by side, each explicitly attributed** ("longevity says X, integrate says Y"). Never average or collapse them into one verdict that hides which discipline actually won — that tension is the point.
4. **cupertino-council** — for any user-facing surface in scope.
5. **cupertino-prototype** — only if a genuine empirical uncertainty exists in this scope. If there is no specific answerable question to settle empirically, **report this stage as explicitly skipped** ("no empirical uncertainty identified for this scope — skipped"), never omit it silently and never as "not applicable."
6. **cupertino-elevate** — only if something already in scope is a low-status commodity feature worth transfiguring. If nothing qualifies, **report as explicitly skipped**, same rule as above — don't invent a candidate to avoid an empty stage.
7. **cupertino-unbox** — for the first five minutes of the resulting build, if applicable to this scope.
8. **cupertino-reveal** — the final automatic stage. Exactly one built suggestion.

## Cannibalization — never automatic

Do not invoke `cupertino-cannibalize` as part of this pipeline, ever — it is user-invoked only, and the PreToolUse hook will refuse it anyway while `review-pipeline-active` is set. If, while running the other stages, a genuine cannibalization question emerges organically (something currently successful that a team member is implicitly asking whether to replace), **flag it explicitly at the end of the review** and suggest the user invoke `cupertino-cannibalize` separately, on its own, after this review concludes. Do not answer that question inline as part of this pipeline.

## Output format

Present each stage's result in sequence, in the fixed order above. For stage 3, use the explicit side-by-side attribution format. For stages 5 and 6, report "skipped" plainly wherever they don't apply. End with the built reveal, and the cannibalization flag if one emerged.
