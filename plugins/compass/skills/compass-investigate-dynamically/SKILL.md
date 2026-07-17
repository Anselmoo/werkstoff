---
name: compass-investigate-dynamically
description: >-
  Investigates a task whose sequence of actions or tool calls cannot be
  planned upfront, because each step's result determines what the next step
  should be. Use this when the path to an answer is genuinely unknown at the
  start — open-ended research, tracing an unfamiliar codebase, diagnosing a
  live failure, answering a factual question that requires lookup rather
  than recall, or any task where committing to a fixed tool order in advance
  would mean guessing at steps 2 through N before step 1 even returns.
  Distinct from compass-decompose-chain, which is for tasks whose stages ARE
  already knowable upfront and only need to be sequenced with input/output
  contracts — this skill is for tasks where the stages are NOT yet knowable,
  and only become clear one observation at a time.
---

Run a task as a single agent's own turn-by-turn investigation loop within
the current conversation — never as a fan-out to other agents, and never
by pre-committing to a fixed sequence of tool calls. This is the plugin's
mechanism for tasks that fail the precondition `compass-decompose-chain`
requires: a plannable, fixed set of 2-5 stages known before execution
starts. When that precondition doesn't hold — the next useful action
depends on what the last tool call actually returned — use the loop below
instead.

This generalizes two techniques that share one underlying structure:
`art.prompt.md` (Reasoning / Tool-call / Result,
selecting a tool from a library only when a step genuinely needs it) and
`react.prompt.md` (Thought / Action / Observation, with an
explicit "look it up, don't guess" discipline). Both templates converge on
the same three-part step; this skill names that shared structure
**Reasoning / Action / Observation**. Three further documented variants
sit along the same escalation spectrum, each detailed in its own
knowledge doc rather than restated here: `rewoo.md` (plan every call
upfront, cheaper when calls are expensive and don't need mid-execution
adaptation), `self-ask.md` (a minimal follow-up-question chain, the
lightest-weight entry point), and `lats.md` (branch, score, and backtrack
across candidate action sequences, for investigations one linear trace
can't reliably resolve).

## When this applies, vs. `compass-decompose-chain`

| | `compass-decompose-chain` | `compass-investigate-dynamically` |
|---|---|---|
| Stages known | Upfront, before execution starts | Only discovered as each step returns |
| Plan shape | Fixed 2-5 stages with explicit input/output contracts | No fixed plan — one step decided at a time |
| Failure this prevents | Skipping verification between stages | Guessing the rest of the sequence before seeing step 1's result |

If a task can be broken into stages by reading the request alone — without
running anything first — it is a `compass-decompose-chain` task, even if
it is long. Reach for this skill only when that breakdown genuinely can't
be done in advance: the request itself is "find out X" or "fix Y" with no
known map of how to get there.

## The Reasoning / Action / Observation loop

Run each step in this exact shape, and show the shape explicitly rather
than folding it into prose:

```
Step N
Reasoning: <what is still unknown, and why this specific action resolves it>
Action: <tool/skill name>(<arguments>)
Observation: <what the action actually returned>
```

- **Reasoning names a real gap.** Write down what is still unknown before
  choosing the action — not a justification invented after the fact for an
  action already decided on.
- **Action is chosen dynamically, from whatever is actually available in
  this session** — file tools, search, a sub-shell command, or another
  `compass-*` skill (e.g. `compass-ground-evidence` to force a citation on
  a claim just surfaced, `compass-reason-verify` if a step turns out to be
  a hard reasoning problem in its own right) — not a pre-declared list
  fixed before Step 1. Never call a tool "to be thorough" or "in case it's
  useful" — only when the current Reasoning line names a gap that
  specific action closes. An unnecessary call burns context and dilutes
  the trace's audit value.
- **Observation is the actual return value, not a summary written to fit
  the expected answer.** If a step returns nothing useful, say so and let
  the next Reasoning line adjust — do not quietly discard a bad result and
  re-ask the same question hoping for a better one.

**Look it up, don't guess.** Any factual claim the investigation depends
on — a current value, a specific file's actual content, an API's actual
behavior, a config's actual current state — gets an Action that retrieves
it. Do not fill a gap with plausible-sounding prior knowledge and move on;
that is exactly the failure mode both source techniques exist to prevent
(ReAct forces retrieval over confident recall; ART's tool-selection exists
because a fixed guessed sequence breaks the moment reality diverges from
the guess).

Repeat Step N as many times as the task's actual unknowns require — there
is no fixed count. Two consecutive steps whose Reasoning lines no longer
name a new unknown (the remaining actions are now obvious and fixed) is a
signal the investigation has resolved into a knowable sequence; finish it
as plain steps rather than manufacturing artificial uncertainty to keep
the loop format going.

## Ending the loop

Close every investigation with a clearly labeled final section, once the
Reasoning line concludes no further action is needed to answer the task:

```
Final output:
<the result that directly answers or fulfills the task, citing which
Observations it rests on>
```

Every claim in the Final output must trace back to an Observation in the
trace above it, or be explicitly flagged as prior knowledge rather than
looked-up fact — do not let the Final output assert anything the loop
itself never actually observed.

## Cross-cutting constraints

Source techniques (vendored locally, no external repo dependency):
`../../references/knowledge/react.md`,
`../../references/knowledge/art.md`,
`../../references/knowledge/rewoo.md`,
`../../references/knowledge/self-ask.md`, and
`../../references/knowledge/lats.md` — see `../../references/knowledge/index.md`.

See `../../references/constraints.md` for the context-rot and
plausible-vs-verified constraints that apply to every `compass-*` skill,
including this one — an investigation loop is exactly where the naive
instinct to "add more context" or "sound confident" instead of stopping to
verify shows up most.
