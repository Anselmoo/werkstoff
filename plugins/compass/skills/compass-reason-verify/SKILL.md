---
name: compass-reason-verify
description: Applies escalating reasoning rigor, beyond Claude's ordinary single-pass reasoning, when a task shows a concrete failure-mode signal — multi-step arithmetic or dependent calculations prone to an intermediate error, a puzzle/decision with one unique correct answer where a wrong early assumption is costly, precision-critical arithmetic better offloaded to code, or an image/diagram that must be described before it's reasoned about. Covers real-world high-stakes calculations where a mistake has consequences — compound interest, loan amortization, unit conversions, dosage or measurement calculations — not just abstract puzzles or math-homework framing. Use only when one of these specific signals is present — not for ordinary questions, casual explanations, or any task where Claude's default reasoning is already sufficient; most requests do not need this skill. Composed automatically by compass-solve's Execute phase when a stage's content matches one of these signals; invoke standalone when the user explicitly asks to "show your work", "verify this calculation", "double-check this reasoning", "walk through this carefully, I can't afford a mistake", or "solve this step by step and check the answer".
---

Reason through a task with exactly as much structure as its stakes and
failure mode require — never less than the task needs, never more than it
needs. This skill's methodology is an explicit **four-rung escalation
ladder** plus one **triggered mode**, each rung built on a named technique
from `universal-creator`'s prompt-engineering templates, generalized beyond
their example domains (legal clauses, word problems, logic puzzles) to any
reasoning task. Techniques are internal mechanism only — never announce
"switching to chain-of-thought" to the user; just reason at the rung the
task calls for.

Source techniques (vendored locally, no external repo dependency):
`../../references/knowledge/zero-shot.md`,
`../../references/knowledge/cot.md`,
`../../references/knowledge/self-consistency.md`,
`../../references/knowledge/pal.md`, and
`../../references/knowledge/multimodal-cot.md` — see `../../references/knowledge/index.md`.

See `../../references/constraints.md` for the context-rot and
plausible-vs-verified constraints that apply across every `compass-*`
skill, including this one — plausible-vs-verified matters especially here:
a confident-sounding reasoning chain is not evidence it's correct.

## The escalation ladder

Climb only when the **concrete signal** below actually applies — not on a
vague sense that a task "seems important." Each signal mirrors the exact
rationale the source template gives in its own "Why this technique" /
"When to escalate" section.

| Rung | Technique | Built on | Concrete signal to climb here from the rung below |
|---|---|---|---|
| 0 | Zero-shot | `zero-shot.prompt.md` | *(starting rung — see "Choosing the starting rung" below)* |
| 1 | Chain-of-Thought (default) | `cot.prompt.md` | The task involves **more than one dependent calculation or inferential step** — zero-shot tends to set a problem up correctly but get an intermediate step wrong when nothing forces the model to show its work. |
| 2a | Self-consistency | `self-consistency.prompt.md` | The task has a **single, unique correct answer** and the stakes of a wrong answer are high enough that **one reasoning path making an early wrong assumption** is a real risk — not every CoT task needs this, only ones where a single misstep silently propagates to a wrong final answer. |
| 2b | PAL (code offload) | `pal.prompt.md` | The calculation involves **many variables, conditional logic, large numbers, or a long chain** likely to produce rounding/carry errors in mental arithmetic — precision matters more than showing reasoning steps in prose. |
| — | Multimodal-CoT (triggered mode, not a rung) | `multimodal-cot.prompt.md` | The input **includes an image or diagram** — this triggers regardless of which rung the underlying reasoning otherwise needs, and runs *before* that rung's own reasoning starts. |

### Choosing the starting rung

Do not always start at rung 0. Assess the task once, up front:

- Output format is fully specified, the task falls within common,
  well-trodden domain knowledge, and it resolves in a single pass with no
  dependent intermediate steps → start at **Rung 0 (zero-shot)**.
- Any multi-step arithmetic, multi-step deduction, or dependent
  intermediate values are involved → start at **Rung 1 (CoT)**, the default
  for most non-trivial reasoning tasks.
- The task is a puzzle/decision with a unique correct answer where getting
  it wrong is costly, or involves precision-critical arithmetic from the
  outset → start directly at **Rung 2a or 2b** — climbing through 0 and 1
  first adds no value when the signal is already present at task intake.
- The input includes an image/diagram → apply **Multimodal-CoT** first,
  regardless of which rung the reasoning itself will need once the visual
  content has been described.

## Rung 0 — Zero-shot

No extra structure. Answer directly, but hold the output to whatever fixed
format the task specifies (per `zero-shot.prompt.md`: a
defined structure, a defined length, no jargon left undefined). This is the
floor, not a fallback to use out of laziness — use it only when the
starting-rung check above actually lands here.

**Escalate immediately if:** key nuances get missed (carve-outs,
cross-references, edge cases the fixed structure didn't anticipate) — that
signal calls for `compass-calibrate-format`'s few-shot anchoring, not this
ladder's rungs; note it and hand off.

## Rung 1 — Chain-of-Thought (default)

Write out every step explicitly, labeled (Step 1, Step 2, …), and end with
a single clearly labeled final-answer sentence — never skip a step to save
space, and never state the answer before the steps that justify it.

```
Step 1 — <what this step computes/establishes>
Step 2 — <...>
...
The answer is: <final answer stated plainly>
```

This is where most non-trivial `compass-solve` stages land. Stay here
unless one of Rung 2a/2b's concrete signals is actually present.

## Rung 2a — Self-consistency (parallel paths, majority vote)

Reason through the task **three times independently**, each pass using a
genuinely different strategy — not three restatements of the same
approach:

1. **Forward deduction** — work from the given facts forward, eliminating
   impossible options as you go.
2. **Backward from options** — start from each candidate answer and check
   which one is consistent with all the facts.
3. **Constraint mapping** — list every constraint explicitly, then check
   which candidate satisfies all of them simultaneously.

**Preferred — Workflow orchestration.** If the **Workflow tool** is
available in this session (this skill invocation is your authorization):

```
Workflow({
  scriptPath: "${CLAUDE_PLUGIN_ROOT}/workflows/reason-verify-scan.js",
  args: { reasoningTask: "<the task/puzzle/problem text>", strategies?: ["forward deduction", "backward from options", "constraint mapping"], _contractVersion: "compass-contract-v1" }
})
```

It dispatches one `reasoning-path` agent per strategy in parallel (each
attempt is genuinely independent — no agent sees another's work), then
computes a deterministic majority over the three answers. Returns
`{attempts: [{strategy, answer, reasoning}], majorityAnswer,
agreementCount, dissentingAttempts}`.

**Fallback** (no Workflow tool) — spawn three `reasoning-path` subagents
directly, one per strategy above, each with the task text and the
untrusted-content discipline the agent file documents. Collect each
`{strategy, answer, reasoning}`, then apply the identical deterministic
majority logic `reason-verify-scan.js` uses (normalized string equality on
`answer`; see next section for its limits) rather than eyeballing it.

### Answer-comparison limits — read before trusting `agreementCount`

`reason-verify-scan.js` computes majority by exact string equality on a
normalized (trimmed/lowercased/whitespace-collapsed) `answer` field. This
works cleanly for a single number, a short canonical phrase, or one option
label — and breaks down the moment answers are equivalent but not
identically formatted ("8" vs "eight" vs "$8.00"), or expressed as longer
prose that paraphrases the same conclusion, or as a structured object whose
key order/formatting differs between attempts. The workflow script
documents this in a code comment rather than silently pretending automatic
comparison always works. When `dissentingAttempts` look like paraphrases of
the same conclusion rather than genuine disagreement, read each attempt's
`answer` and `reasoning` and judge equivalence directly — do not report
`agreementCount` as a verified consensus without that check.

**If all three attempts genuinely disagree** (`majorityAnswer` is `null`):
per `self-consistency.prompt.md`'s own instruction, identify
the attempt supported by the strongest reasoning chain and explain why the
other two failed — this is a judgment call for this skill to make by
reading the three `reasoning` fields, not something the workflow computes.

**Optional — render an interactive trace.** `compass` has no
`output_dir`/settings file, so this is opt-in visualization, not a required
report. After presenting the majority/dissent result below, optionally
render the self-consistency result (the object returned above:
`{attempts, majorityAnswer, agreementCount, dissentingAttempts, ...}`) as
an interactive convergence diagram — three parallel reasoning lanes meeting
at one majority-answer node, dissenting attempts visually distinguished —
via `${CLAUDE_PLUGIN_ROOT}/assets/reasoning-trace-viewer.html`, using the
same injection approach `self-assess-stage-map` uses for
`topology-viewer.html` (JSON-safe-escape `<`/`>`/`&` before injecting into
the `<script>` block — do not reimplement that escaping ad hoc):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/references/render_trace.py" \
  "${CLAUDE_PLUGIN_ROOT}/assets/reasoning-trace-viewer.html" <output-path> <<'JSON'
<the workflow's actual JSON result, verbatim>
JSON
```

Pick a reasonable `<output-path>` (a scratch/tmp file, or a path the user
suggests). If it renders, tell the user they can view the reasoning trace
interactively at that path — never present this as a required step, and
only offer it for this self-consistency rung (2a), not the other rungs on
the ladder, which have no structured multi-path result to visualize.

**Escalate from here if:** the task requires more than roughly 10 logical
steps to resolve — fitting three independent full attempts in a single
turn stops being practical. Hand off to `compass-decompose-chain` to solve
one sub-problem per stage instead of forcing self-consistency to scale.

## Rung 2b — PAL (Program-Aided Language, code offload)

Translate the problem into a Python `solve()` function with descriptive
variable names and a comment per line explaining what each variable
represents, execute it, then state the answer in a plain-language sentence
— never skip straight to a numeric answer without the code, and never trust
mental arithmetic over the executed result once code is in play.

```python
def solve():
    # <variable> = <value>  # <what this represents>
    ...
    return answer

print(solve())
```

Python arithmetic is exact for integers and IEEE 754 for floats; mental
arithmetic chains accumulate errors. PAL leaves Claude responsible only for
problem parsing (where it's strong) and code for computation (where
precision matters).

**Escalate from here if:** the problem involves symbolic math (integrals,
matrix operations) → use a `sympy`-based solution instead of plain
arithmetic. If the problem needs external data (prices, exchange rates,
current values) → combine with `compass-ground-evidence` to source and cite
that data before generating the code, rather than hardcoding a guessed
value.

## Multimodal-CoT — triggered mode for image/diagram input

Whenever the input includes an image or diagram, run this four-step
process **before** any of the rungs above, regardless of which rung the
underlying reasoning otherwise needs. **Never answer first and justify
after** — that ordering is exactly the failure mode this mode exists to
prevent.

1. **Describe (visual inventory)** — without attempting to answer yet,
   describe everything visible: text labels, numbers, annotations, shapes,
   arrows, connections and their directions, colors/patterns if they carry
   meaning, scale/axes/legend if present.
2. **Identify relevant components** — from the description, list which
   elements are directly relevant to the question and why each matters.
3. **Reason** — using only the identified elements, reason step by step
   (trace a process flow explicitly if the image is a diagram; read values
   precisely if it's a chart).
4. **Answer** — state the answer clearly, citing which reasoning step
   supports it. An exact value for numeric answers, a named option plus its
   supporting step for a decision/conclusion.

After this mode completes Step 4, feed its answer into whichever rung
(0/1/2a/2b) the underlying reasoning task needs — multimodal-CoT replaces
the "read the input" phase of that rung, not the reasoning itself.

**Escalate/adjust from here if:** image quality is poor or labels are
ambiguous → ask the user for a text transcription of the labels before
Step 1 rather than guessing at illegible content. Multiple images must be
compared → hand off to `compass-decompose-chain` for one Multimodal-CoT
pass per image followed by a synthesis stage, rather than cramming multiple
descriptions into one pass.

## Present

State which rung (or triggered mode) was used, in plain language tied to
*why* — the concrete signal that triggered it, not the technique's name as
jargon. For self-consistency, report `agreementCount`/3 and, if
`dissentingAttempts` is non-empty, whether they were resolved as genuine
disagreement (strongest-chain judgment made) or as paraphrases of the same
answer (comparison-limits note applied). For PAL, show the executed code
alongside the plain-language answer. For multimodal-CoT, keep the
Describe → Identify → Reason → Answer structure visible in the final
response rather than collapsing it down to just the answer.
