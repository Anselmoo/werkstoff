---
name: cupertino-backwards
description: "Use FIRST, before cupertino-focus or any other cupertino technique, whenever customer experience and technology choices are both still undecided for a new feature or project scope. This is a pre-architecture gate: it establishes what experience actually matters before any technology direction is chosen, working backwards from experience to technology rather than forwards from the feature request. Trigger on requests like 'design a way for users to...', 'we need a feature that...', or any new scope where nobody has yet named a database, framework, API, or UI element."
---

Work backwards from customer experience to technology. Never accept the literal feature request as the destination — the destination is the experience, and technology is only ever a means to it.

## Steps

1. **State the literal request** exactly as given, verbatim or near-verbatim.
2. **State the underlying problem** — the actual friction or desire this request is trying to resolve for a person, independent of any implementation. If the literal request and the underlying problem turn out to be identical (the request already is the problem, with nothing lost in translation), say so explicitly rather than manufacturing a distinction.
3. **Write the customer experience statement**: exactly one sentence, in plain human language, describing what the experience should feel like. It must contain **zero technology nouns** — no database, framework, API, widget, button, screen, endpoint, component, or similar. If you catch yourself reaching for one, the sentence has already smuggled in a technology answer; rewrite it in terms of what the person does or feels instead.
4. **Validate mechanically** — do not eyeball this. Run:
   ```bash
   echo '{"statement": "<your one-sentence statement>"}' | python3 "${CLAUDE_PLUGIN_ROOT}/scripts/validators.py" zero-tech-nouns
   ```
   If it exits non-zero, the statement failed and lists which words tripped it — rewrite the sentence, don't argue with the checker.
5. **Choose a technology direction** only now, after the experience statement passes. Explain concretely how the chosen direction serves that statement — not "these are popular tools" but "this is what makes the felt experience possible."
6. **Flag drift risk**: name the specific points later in the build where the technology direction might tempt scope to drift away from the experience statement (e.g. "it will be tempting to add a settings screen here — that serves configurability, not the stated experience").

## Mark the gate as passed

Every technique later in the cupertino pipeline that commits to architecture or design (`cupertino-focus`, `cupertino-longevity`, `cupertino-integrate`, `cupertino-council`) is blocked by a PreToolUse hook until this marker exists for the current repo. The hook only checks that the marker file exists — it never reads its content — so the marker's value is free to carry the real output forward instead of a placeholder:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/state.py" init
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/state.py" set backwards-done '{"literalRequest":"...","underlyingProblem":"...","statement":"...","techDirection":"...","driftRisks":["..."]}'
```

Use the actual content from steps 1-6 above as that JSON's values — not a placeholder "1". This is what lets `cupertino-review` (and anything else invoking this stage as part of a pipeline) read back a real, structured result via `state.py check backwards-done` instead of only knowing the gate passed with no idea what was decided.

Run this only after step 4 has actually passed — do not set the marker preemptively or on a failed validation.

## Output format

Present, in this order: the literal request, the underlying problem (or the explicit "these are the same" flag), the validated experience statement, the chosen technology direction with its justification, and the drift-risk points. Do not skip straight to a technology recommendation.
