---
name: compass-optimize-instruction
description: Optimizes the exact wording of an instruction/prompt for a recurring task — one that will be reused many times, not answered once. Use this when asked to write, tune, or improve a system prompt, classifier prompt, agent instruction, or any other instruction template that runs repeatedly, especially once representative test cases (inputs with their expected outcomes) are available to score candidates against. Do not use this to audit, lint, or critique an arbitrary existing prompt someone else wrote with no plan to regenerate it — that is explicitly out of scope; see Non-goal below.
---

Optimize the wording of an instruction for a **recurring** task using APE
(Automatic Prompt Engineer) to generate and score multiple candidates, then
meta-prompting's critique-and-revise discipline on the winner only.

## Non-goal — read this first

This skill is **not** a general-purpose prompt linter. It does not audit,
score, or critique an arbitrary existing prompt just because it's handed one
— it optimizes wording for a task the user will run *again and again*, via
generate → test → select, and it needs representative test cases to do that
honestly. If the ask is "review/improve this prompt" with no recurring-use
context and no way to test candidates against real cases, that's a
`compass-draft-revise` job (revise against stated criteria) or a
`compass-ground-evidence` job (check factual claims), not this skill. Ask
which is actually meant before running the workflow below if it's unclear.

Source techniques (vendored locally, no external repo dependency):
`../../references/knowledge/ape.md` and
`../../references/knowledge/meta-prompting.md` — see `../../references/knowledge/index.md`.

See `../../references/constraints.md` for the plausible-vs-verified and
context-rot constraints this skill inherits — a candidate that "looks like"
it would pass a test case is not the same as one that's actually been scored
against it, which is exactly why scoring happens per test case rather than
by inspection alone.

## Step 0 — Establish the recurring task and its test cases

Confirm two things before invoking the workflow:

1. **The recurring task description** — what the instruction needs to make
   the model do, each time it runs. If this arrives from `compass-solve`'s
   Execute phase (a stage whose deliverable is itself an instruction), use
   the stage's contract as the task description directly.
2. **3-5 representative test cases**, each an `{input, expectedOutcome}`
   pair. These must be **real, representative cases** — not invented inside
   this skill or the workflow it calls. Source them, in order of
   preference: (a) test cases already supplied by the caller (e.g.
   `compass-solve` passing along a stage's own examples), (b) the user's own
   prior inputs/outputs for this recurring task, (c) cases elicited directly
   from the user if neither of the above exists. If no test cases can be
   obtained at all, say so plainly and ask the user for at least a few
   before proceeding — do not fabricate plausible-looking cases and pass
   them off as representative; `optimize-instruction-scan.js` refuses to
   invent its own for the same reason.

## Step 1 — Run the optimization

**Preferred — Workflow orchestration.** If the **Workflow tool** is
available in this session (this skill invocation is your authorization):

```
Workflow({
  scriptPath: "${CLAUDE_PLUGIN_ROOT}/workflows/optimize-instruction-scan.js",
  args: { taskDescription: "<the recurring task description>", testCases: [{input, expectedOutcome}, ...], _contractVersion: "compass-contract-v1" }
})
```

This runs three phases:

1. **Generate** — five `instruction-candidate` agents in parallel, one per
   APE framing (rule-based, example-based, definition-based, question-based,
   chain-of-thought-based), each drafting one candidate instruction fully
   committed to its assigned framing.
2. **Score** — one `instruction-candidate` agent per candidate, evaluating
   it against the exact test cases from Step 0 (never re-invented inside
   the workflow) and reporting a pass/fail per case plus a total score. The
   winner is selected deterministically in plain JS afterward (highest
   score, ties broken by APE's own framing order) — no agent is asked to
   also make the selection call.
3. **Critique** — one `instruction-candidate` agent applies meta-prompting's
   four-item checklist (behavioral rules unambiguous? handles out-of-scope
   requests? output-format rules mutually compatible? any instruction
   two-ways-interpretable?) to the **winning candidate only**, revising only
   the failing portions if any criterion fails.

Tell the user the candidate/framing count before launching. The candidate
agents are read-only by design; **you** present the result below.

**Fallback** (no Workflow tool) — spawn one `instruction-candidate` subagent
per APE framing in parallel for Generate (same brief the workflow gives each
one — see `workflows/optimize-instruction-scan.js`'s `FRAMINGS` array for
the exact per-framing hints), then one subagent per candidate for Score
against the same test cases, then select the highest-scoring candidate
yourself (ties broken by framing order: rule-based, example-based,
definition-based, question-based, chain-of-thought-based), then dispatch one
final `instruction-candidate` subagent in Critique mode against the winner
only.

## Step 2 — Present the result

Report, in order:

- **Candidates table**: framing, score (`n`/total test cases) for all five
  — this shows the comparison the selection was based on, not just the
  winner in isolation.
- **Winner**: which framing won and why (its score relative to the others).
- **Critique checklist**: each of the four criteria with pass/fail and the
  one-sentence note, so the user can see exactly what (if anything) the
  revision pass changed and why.
- **Final prompt**: the `finalPrompt` from the workflow result, in a fenced
  code block, ready to use — this is the actual deliverable.

If the task's deliverable feeds back into a `compass-solve` pipeline stage,
return `finalPrompt` to that stage rather than treating this as a
standalone endpoint — this skill is callable from within `compass-solve`'s
Execute phase but is not itself a pipeline phase.

## Optional — render an interactive trace

`compass` has no `output_dir`/settings file, so this is opt-in
visualization, not a required report — offer it, don't gate on it. After
presenting Step 2, optionally render the workflow's result (the object
returned in Step 1: `{candidates, winner, critiqueChecklist, finalPrompt}`)
as an interactive candidate diagram via
`${CLAUDE_PLUGIN_ROOT}/assets/reasoning-trace-viewer.html`, using the same
injection approach `self-assess-stage-map` uses for `topology-viewer.html`
(JSON-safe-escape `<`/`>`/`&` before injecting into the `<script>` block —
do not reimplement that escaping ad hoc):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/references/render_trace.py" \
  "${CLAUDE_PLUGIN_ROOT}/assets/reasoning-trace-viewer.html" <output-path> <<'JSON'
<the workflow's actual JSON result, verbatim>
JSON
```

Pick a reasonable `<output-path>` (a scratch/tmp file, or a path the user
suggests). If it renders, tell the user they can view the reasoning trace
interactively at that path — never present this as a required step.
