---
name: compass-reason-verify
description: >-
  Matches reasoning effort to concrete failure-mode signals by climbing a 4-rung
  ladder — zero-shot, Chain-of-Thought, Self-consistency, or PAL (code offload) —
  and applies Multimodal-CoT first when the input has an image or diagram. Use
  when a task shows a real risk of a silent reasoning error: multi-step
  arithmetic, a single-correct-answer puzzle where a wrong early assumption is
  costly, a precision-critical calculation, or an image/diagram input. Not for
  well-trodden single-step questions.
---

# compass-reason-verify

Pick the rung from **concrete signals**, then reason at that rung. The guard
selects the rung deterministically and enforces the self-consistency count.

`GUARD="python3 ${CLAUDE_PLUGIN_ROOT}/scripts/compass.py"`

## Select the rung (guarded)

Describe the task's signals and let the guard choose:

```
echo '{
  "has_image_or_diagram":false,
  "multistep_arithmetic":true,
  "dependent_intermediate_values":true,
  "single_correct_answer":false,
  "costly_wrong_assumption":false,
  "precision_arith":false,
  "many_variables":false,
  "large_numbers":false,
  "rounding_risk":false,
  "conditional_logic":false
}' | $GUARD rung -
```

The guard returns `rung`, `multimodal_cot_first`, and `self_consistency_paths`.
**Climb the ladder only when concrete signals apply:**

- **Rung 0 (zero-shot)** — only when the output format is fully specified, there is
  no multi-step arithmetic, and no dependent intermediate values. The guard
  refuses Rung 0 when dependent steps exist.
- **Rung 1 (Chain-of-Thought)** — the default for multi-step reasoning. **Label
  each step (Step 1, Step 2, …) and end with a single clearly labeled final-answer
  sentence.**
- **Rung 2a (Self-consistency)** — when a single correct answer exists and a wrong
  early assumption is costly. Produce **exactly 3 independent attempts**, one per
  strategy: forward deduction, backward from options, constraint mapping. Then
  take the majority.
- **Rung 2b (PAL)** — when there are many variables, conditional logic, large
  numbers, or rounding risk: offload the computation to code.

**If the input includes an image or diagram, apply Multimodal-CoT BEFORE any
rung's reasoning** (`multimodal_cot_first: true`), regardless of the rung chosen.

## Self-consistency (Rung 2a)

Prefer the workflow `${CLAUDE_PLUGIN_ROOT}/workflows/reason-verify.js` (args
`{ task, hasImageOrDiagram? }`) — it dispatches three isolated `reasoning-path`
agents in parallel and votes. Otherwise dispatch three isolated attempts yourself
and validate:
```
echo '{"attempts":[
  {"strategy":"forward deduction"},
  {"strategy":"backward from options"},
  {"strategy":"constraint mapping"}]}' | $GUARD self-consistency -
```
The guard requires **exactly 3** attempts covering all three strategies.

## Output
- reasoning structured to the selected rung
- the final answer derived from that reasoning
