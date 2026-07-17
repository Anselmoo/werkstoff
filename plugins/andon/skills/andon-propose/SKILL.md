---
name: andon-propose
description: Proposes a fix for one gap maximally — from the codebase, the ledger's written artifacts, and domain best-practice — then grills the user one question at a time, only on genuinely load-bearing forks, each question paired with a recommended answer and a blast-radius/reversibility tag. Use this when andon-loop needs to decide what to fix next, or directly when the user asks "what should I fix here", "propose a fix for this gap", "grill me on this decision", or "what's the load-bearing question here".
---

Propose a fix for exactly one gap, maximally, before asking the user
anything — then interview the user only on the residual forks that
genuinely can't be resolved alone. This is `andon-loop`'s Phase 3 ("pick
one gap by priority" already having happened upstream — this skill
proposes *how* to fix the one gap handed to it) — restructured from the
personal `autonomous-grilling` skill's propose-then-grill discipline,
plus one output field that discipline didn't have: every proposed fix is
tagged with a blast-radius/reversibility rating that feeds `andon-loop`'s
stop rule.

Full checklist and red-flag table: `${CLAUDE_PLUGIN_ROOT}/skills/andon-verify/references/grilling-protocol.md`
(shared location — `andon-verify`'s references directory is this
plugin's single reference library, not a strategy-specific one; see that
file's own header for why it lives there rather than being duplicated).

## Input

Called with one gap (from `andon-loop`'s Phase 2 scan, or named directly
by the user): its `kind` (`bug` | `feature` | `wire`), which stage/wire
it's on, and any ledger context (prior gap docs, evidence docs already
linked to this stage). If called standalone (no `andon-loop` context),
treat the user's description as the gap.

## Phase 1 — Propose (autonomous, do this first)

Before asking anything:

1. **Read the written record.** The ledger's stage doc and any linked
   gap/evidence docs for this stage (see
   `andon-verify/references/okf-ledger-schema.md` for the frontmatter
   shape), `.claude/house-rules.md` if `andon-preflight` found one, and
   `CLAUDE.md`/ADRs. Do not ask the user what is already written down.
2. **Explore the codebase.** Read the stage(s) either side of the
   affected wire — symbols, files, patterns, conventions actually in use
   nearby. Anything answerable by reading code is *not* a question.
3. **Draft one concrete fix.** State: the proposed change, why, the
   files it touches, and which `andon-verify` strategy will prove it
   (name the strategy and one-line why — this is decided here, not left
   for `andon-verify` to guess; see that skill's
   `references/wire-classifier.md` for the routing logic this proposal
   should already anticipate).
4. **Tag blast radius** — exactly one of:
   - `local+reversible` — confined to one stage, trivially undoable.
   - `hard-to-reverse` — crosses a stage boundary, touches a public
     signature/schema, or would be costly (not impossible) to undo.
   - `shared-state-visible` — touches persisted data, a migration, a
     published artifact, or anything another party could already depend
     on before a revert lands.

   This directly extends the standard Claude Code harness doctrine
   ("Executing actions with care": reversible/local actions proceed
   freely; hard-to-reverse or shared-state-visible actions require
   explicit confirmation) into this loop's decision output. It is read
   downstream by `andon-loop`'s stop rule condition 2 — a tag exceeding
   the loop's configured `authorization_level` (see
   `references/settings.md`) halts the loop rather than auto-advancing,
   regardless of how confident the fix looks otherwise.

Output of Phase 1: a draft fix where the approach, verification
strategy, and blast-radius tag are already decided and justified — not a
menu of options.

## Phase 2 — Grill (relentless, but only the residue)

Interview the user only on what Phase 1 could not resolve alone:

- Walk open forks one at a time, resolving the fork that unblocks the
  most downstream decisions first.
- For each question, **give your recommended answer** and a one-line
  rationale — never a bare option list.
- One question per turn. Wait for the answer before asking the next.
- **A `hard-to-reverse` or `shared-state-visible` tag is always a
  load-bearing fork**, even when the fix itself looks obvious — confirm
  the scope of authorization, not the fix's correctness. A
  `local+reversible` tag is never itself a reason to grill.
- If a question can be answered by reading more code, go read more code
  instead of asking.
- Default to your recommendation on "proceed" / "your call" / silence.

## Output

Return (to `andon-loop`, or print directly if standalone):

```
Fix: <one paragraph — what, where, why>
Touches: <file list>
Verification strategy: <andon-verify strategy letter + name>
Blast radius: local+reversible | hard-to-reverse | shared-state-visible
Open forks resolved: <question → answer, one line each, or "none — fully
  resolved from codebase + best-practice">
```

`andon-loop` passes this straight to `andon-verify` as the wire-proof
input, and records the blast-radius tag in the gap's OKF doc frontmatter
(`references/okf-ledger-schema.md`) before evaluating the stop rule.

## Red flags (you're doing it wrong)

See the full table in `grilling-protocol.md`; the two specific to this
skill's new field:

| Symptom | Fix |
|---|---|
| Proposing a fix with no blast-radius tag | Every proposal gets exactly one tag — never optional. |
| Treating `hard-to-reverse` as "ask if it feels risky" | It is not a vibe check — cross-stage-boundary or public-signature changes are always `hard-to-reverse` at minimum, regardless of how simple they look. |
