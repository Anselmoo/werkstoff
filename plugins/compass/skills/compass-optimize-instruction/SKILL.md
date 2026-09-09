---
name: compass-optimize-instruction
description: >-
  Optimizes the exact wording of an instruction/prompt for a recurring task using
  APE — generates one candidate per framing, scores them against real test cases,
  and critiques the winner. Use when a prompt will be reused and its wording
  matters: "tune this prompt", "find the best wording for this instruction",
  "optimize this system prompt", "which phrasing works best", with representative
  test cases available. Not for one-off prompts with no test cases.
---

# compass-optimize-instruction

Generate 5 framings, score on fixed test cases, select, critique the winner. The
guard enforces the candidate count, the framing set, the tie-break, and the
checklist size in code.

`GUARD="python3 ${CLAUDE_PLUGIN_ROOT}/scripts/compass.py"`

## Preferred path: the workflow
When the Workflow tool is available, run
`${CLAUDE_PLUGIN_ROOT}/workflows/optimize-instruction.js`
(args `{ taskDescription, testCases:[{input, expectedOutcome}] }`). It dispatches
one `instruction-candidate` agent per framing in parallel, scores each against the
exact test cases, selects with the framing tie-break, and critiques the winner.

## Inputs
- a recurring task description
- **3-5 representative real test cases** `{input, expectedOutcome}`. **Source them
  from real prior inputs first; only construct if none exist. MUST NOT fabricate
  test cases or adjust expected outcomes.**

## Process

1. **Generate exactly 5 candidates — one per APE framing:** rule-based,
   example-based, definition-based, question-based, chain-of-thought-based. Each
   commits fully to its framing (no blending).
2. **Score each candidate against the exact provided test cases** (pass count).
3. **Select the highest score.** Validate the count, framings, and tie-break:

```
echo '{"candidates":[
  {"framing":"rule-based","score":4},
  {"framing":"example-based","score":4},
  {"framing":"definition-based","score":3},
  {"framing":"question-based","score":2},
  {"framing":"chain-of-thought-based","score":4}
]}' | $GUARD candidates -
```
The guard requires exactly 5 candidates covering all 5 framings and **breaks ties
by framing precedence: rule → example → definition → question → CoT.** Use its
`winner`. If the guard rejects the set (wrong count, missing/duplicate framing,
or malformed JSON), regenerate only the missing/duplicate framing(s) and
re-validate. If the guard still rejects after 2 attempts, stop and report which
framing(s) could not be produced rather than looping indefinitely.

4. **Critique the winner only** with meta-prompting's 4-item checklist, revising
   only failing items:
```
echo '{"checklist":[
  {"criterion":"rules unambiguous","pass":true},
  {"criterion":"handles out-of-scope","pass":false},
  {"criterion":"format rules compatible","pass":true},
  {"criterion":"no two-way readings","pass":true}
]}' | $GUARD critique -
```

## Output
- candidates table: framing, score (n/total)
- winner + why
- critique checklist: pass/fail per criterion
- the final prompt, ready to use

Example (task: "triage inbound support tickets by urgency"):

```
| framing              | score |
|----------------------|-------|
| rule-based           | 4/5   |
| example-based        | 4/5   |
| definition-based     | 3/5   |
| question-based       | 2/5   |
| chain-of-thought-based | 4/5 |

Winner: rule-based (tie with example-based and chain-of-thought-based at 4/5;
framing precedence picks rule-based)

Critique:
- [x] rules unambiguous
- [ ] handles out-of-scope -> revised: added an explicit "no urgency signal
      found" fallback clause
- [x] format rules compatible
- [x] no two-way readings

Final prompt:
"""
Classify this support ticket's urgency as high, medium, or low.

- high: mentions data loss, outage, or a billing failure blocking checkout
- medium: a broken feature with a workaround, or a repeat complaint
- low: a question, a feature request, or cosmetic issue
- if no urgency signal is present, classify as low and note "no signal found"

Ticket: {ticket_text}
"""
```
