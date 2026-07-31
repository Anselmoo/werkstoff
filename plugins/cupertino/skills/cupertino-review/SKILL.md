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
for f in backwards-done focus-output longevity-output integrate-output council-output prototype-output elevate-output unbox-output; do
  python3 "${CLAUDE_PLUGIN_ROOT}/scripts/state.py" clear "$f"
done
```

Clearing every stage's flag before starting is deliberate: a stale `backwards-done` (or any
`*-output`) left over from a **previous, unrelated** review would otherwise let this run skip a
stage it hasn't actually done yet for this scope, or thread a prior scope's content into this
one. Every full pipeline run starts from a clean slate — `cupertino-backwards` runs fresh every
time, never reused across separate `cupertino-review` invocations even on a similar-sounding
scope.

Setting `review-pipeline-active` is what makes the PreToolUse hook refuse an automatic dispatch of `cupertino-cannibalize` for the duration of this pipeline — that refusal is intentional, not a bug to route around. Clear every flag when you finish (success, early stop, or the user cancels) — leaving them set would let a future run wrongly treat this one's stages as already done:

```bash
for f in review-pipeline-active backwards-done focus-output longevity-output integrate-output council-output prototype-output elevate-output unbox-output; do
  python3 "${CLAUDE_PLUGIN_ROOT}/scripts/state.py" clear "$f"
done
```

## Thread each stage's real content into the next dispatch — never re-send only the original scope

Every stage below is dispatched with the **original scope string plus every already-completed
stage's actual result** — not the original scope string alone. A stage that only receives the
raw scope has no way to build on what the pipeline already decided; each dispatch prompt must
include, verbatim, the reported result of every stage that ran before it.

After each stage finishes (except `cupertino-backwards`, which already persists its own result
into `backwards-done` per its own SKILL.md), persist that stage's full reported result — every
field its own Output format / Steps section produced, as JSON — before moving on:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/state.py" set <stage>-output '<json of that stage's full result>'
```

Before dispatching a stage, read back every prior stage's content and include it in the dispatch
prompt:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/state.py" check backwards-done   # -> {"set": true, "value": "<json>"}
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/state.py" check focus-output     # once focus has run
```

If a `check` reports `"set": false` for a stage that should already have run, that stage did not
actually persist its result — stop and fix that before proceeding, don't silently dispatch the
next stage on an incomplete handoff.

## Sequence

1. **cupertino-backwards** — invoke it for real; do not skip straight to focus. It writes the
   `backwards-done` marker (with its full result as content, per its own SKILL.md) other stages
   are gated on.
2. **cupertino-focus** — dispatch with the scope **and** `backwards-done`'s content (the
   experience statement, tech direction, drift risks) included in the prompt. Reduce the
   portfolio implied by this scope. Persist the result to `focus-output`.
3. **cupertino-longevity and cupertino-integrate together** — dispatch each with the scope,
   `backwards-done`'s content, **and** `focus-output`'s content (the cut list and surviving
   items) included in the prompt — an architecture decision made in ignorance of what already
   got cut is a wasted evaluation. Invoke both on the architecture decisions this scope raises.
   **Present both readouts side by side, each explicitly attributed** ("longevity says X,
   integrate says Y"). Never average or collapse them into one verdict that hides which
   discipline actually won — that tension is the point. Persist each to `longevity-output` and
   `integrate-output`.
4. **cupertino-council** — dispatch with the scope plus every prior stage's content included.
   For any user-facing surface in scope. Persist the result to `council-output`.
5. **cupertino-prototype** — dispatch with every prior stage's content included, so the empirical
   question it tests is the one the pipeline actually raised, not a guess reconstructed from the
   scope alone. Only if a genuine empirical uncertainty exists in this scope. If there is no
   specific answerable question to settle empirically, **report this stage as explicitly
   skipped** ("no empirical uncertainty identified for this scope — skipped"), never omit it
   silently and never as "not applicable." Persist the result to `prototype-output` if it ran.
6. **cupertino-elevate** — dispatch with every prior stage's content included. Only if something
   already in scope is a low-status commodity feature worth transfiguring. If nothing qualifies,
   **report as explicitly skipped**, same rule as above — don't invent a candidate to avoid an
   empty stage. Persist the result to `elevate-output` if it ran.
7. **cupertino-unbox** — dispatch with every prior stage's content included. For the first five
   minutes of the resulting build, if applicable to this scope. Persist the result to
   `unbox-output`.
8. **cupertino-reveal** — the final automatic stage, dispatched with every prior stage's content
   included — the one built suggestion must actually draw on what the whole pipeline decided,
   not re-derive it from the original scope alone. Exactly one built suggestion.

## Cannibalization — never automatic

Do not invoke `cupertino-cannibalize` as part of this pipeline, ever — it is user-invoked only, and the PreToolUse hook will refuse it anyway while `review-pipeline-active` is set. If, while running the other stages, a genuine cannibalization question emerges organically (something currently successful that a team member is implicitly asking whether to replace), **flag it explicitly at the end of the review** and suggest the user invoke `cupertino-cannibalize` separately, on its own, after this review concludes. Do not answer that question inline as part of this pipeline.

## Output format

Present each stage's result in sequence, in the fixed order above. For stage 3, use the explicit side-by-side attribution format. For stages 5 and 6, report "skipped" plainly wherever they don't apply. End with the built reveal, and the cannibalization flag if one emerged.
