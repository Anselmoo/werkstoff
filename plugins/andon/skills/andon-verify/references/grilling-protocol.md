# Grilling protocol

Canonical propose-maximally-then-grill checklist for `andon-propose`,
extracted and restructured from the personal `autonomous-grilling` skill.
Read this from `skills/andon-propose/SKILL.md`; do not duplicate it inline.

## Phase 1 — Propose (autonomous, do this first)

Before asking anything:

- **Read the written record.** The ledger's stage/gap/evidence docs, any
  `CLAUDE.md`/`house-rules.md`/ADRs, and whatever `andon-loop` handed off
  about the gap in question. Do not ask the user what is already written
  down.
- **Explore the codebase.** Read the stage(s) either side of the wire the
  gap concerns — symbols, files, patterns, conventions. Anything answerable
  by reading code is *not* a question.
- **Draft the whole fix with a chosen default.** State a **concrete
  proposed fix + why + the files it touches + how it will be verified
  (which `andon-verify` strategy, and why that one)**. Pick the approach,
  the scope, the sequencing. Lead with the answer, not the options.
- **Apply domain best-practice** to make the default defensible, not
  arbitrary — this is what makes the proposal maximal rather than a
  guess.
- **Tag blast radius.** Every proposed fix gets exactly one rating:
  - `local+reversible` — confined to one stage, trivially undoable (a
    local edit, a config value, a comment, a test).
  - `hard-to-reverse` — crosses a stage boundary, touches a public
    signature/schema, or would be costly (not impossible) to undo.
  - `shared-state-visible` — touches persisted data, a migration, a
    published artifact, or anything another party could already be
    depending on before the fix is reverted.

  This tag is not decoration — it is read by `andon-loop`'s stop rule
  (condition 2): a tag exceeding the loop's current `authorization_level`
  halts the loop rather than auto-advancing, the same "reversible/local
  actions proceed freely; hard-to-reverse or shared-state-visible actions
  require explicit confirmation" doctrine the harness already applies to
  tool calls, extended here to this loop's own fix proposals.

Output of Phase 1: a draft fix where the approach, scope, verification
strategy, and blast-radius tag are already decided and justified.

## Phase 2 — Grill (relentless, but only the residue)

Now interview the user until you reach shared understanding on what's
actually load-bearing:

- Walk the proposal's genuinely open forks one at a time, **resolving
  dependencies between decisions first** (a fork that determines the
  answer to three other forks gets asked first).
- For **each** question, **provide your recommended answer** and a
  one-line rationale.
- Ask questions **one at a time**, waiting for feedback before
  continuing. A wall of questions is bewildering and defeats the point of
  proposing maximally first.
- **If a question can be answered by exploring the codebase, explore the
  codebase instead** — go back and read more before asking.

With the autonomy dial turned up:

- **Only escalate genuine forks** — decisions where the options diverge
  in user-visible outcome, cost, or blast radius. A decision with an
  obvious best answer is a Phase-1 default, not a question.
- **Default to your recommendation.** If the user says "proceed", "your
  call", or stays silent on the rationale, take your recommended answer
  and move on.
- **A `hard-to-reverse` or `shared-state-visible` blast-radius tag is
  always a load-bearing fork**, even if the fix itself seems obvious —
  the *scope* of confirmation needed is the genuine question, not the
  fix's correctness. A `local+reversible` tag is never on its own a
  reason to grill.
- Prefer the **smallest load-bearing set** of questions over
  exhaustiveness. If you're about to ask something cosmetic or
  reversible, just decide it and note it.

## Red flags (you're doing it wrong)

| Symptom | Fix |
|---|---|
| Asking something the ledger/codebase answers | Go read it. Not a question. |
| A wall of questions in one message | One at a time. |
| A question with no recommended answer | Always recommend; the user edits, doesn't author. |
| Asking about a `local+reversible` choice | Decide it in Phase 1; mention it, move on. |
| Grilling before proposing | Phase 1 first — propose, *then* grill the residue. |
| Proposing a `hard-to-reverse`/`shared-state-visible` fix without flagging it | The blast-radius tag is not optional; always assign and surface it. |
| "Let me confirm the plan is ok?" as a question | That's the approval gate, not a grill question. |

## Handoff

The approved fix (with its blast-radius tag) goes to `andon-verify` to be
proven, then back to `andon-loop`'s Phase 4 (prove the wire) and Phase 5
(advance) to apply the andon rule's stop conditions.
