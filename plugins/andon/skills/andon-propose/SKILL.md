---
name: andon-propose
description: "Proposes a fix for one gap by reading the ledger and codebase first, then grilling the user one question at a time only on genuinely load-bearing forks. Use when andon-loop dispatches it to propose a fix, or when the user directly asks what to fix for a named gap, or asks to be grilled on a decision."
allowed-tools: "Read, Grep, Glob, Bash"
argument-hint: "<gap-description-or-slug>"
---

# andon-propose

Two phases, strictly in order. Never skip to Phase 2 without finishing
Phase 1's concrete draft first -- interviewing before proposing turns this
into busywork for the user instead of a real proposal to react to.

## Phase 1: propose maximally, then stop drafting

1. Read the gap's stage doc and any docs it links to (prior gap/evidence
   docs in the same stage or wire).
2. Read `.claude/house-rules.md` (or the path in `house_rules_path`
   settings) if `andon-preflight` reported it present. Ground every default
   choice in it -- **never invent a convention the repo already wrote down**,
   and never ask the user something the house-rules file already answers.
   If absent, fall back to codebase-only defaults (read real symbols/patterns
   in the touched stage) without inventing or generating a house-rules file
   yourself.
3. Explore the codebase enough to draft a concrete fix: what changes, which
   files, and why this approach over the obvious alternatives.
4. Choose the `andon-verify` strategy letter this fix should be proven with,
   and write down the rationale in one sentence -- do not leave strategy
   selection to `andon-verify` to guess; you have the most context on the
   gap right now.
5. Assign **exactly one** blast-radius tag. This is mandatory and mechanically
   checked downstream (the ledger schema validator and the PreToolUse hook
   both reject a gap doc with zero, multiple, or an undefined tag) -- do not
   leave it blank meaning to fill it in later.

   - `local+reversible`: confined to one stage, trivially undoable.
   - `hard-to-reverse`: crosses a stage boundary or touches a public signature.
   - `shared-state-visible`: touches persisted data or a published artifact.

   Sanity-check your own tag choice before moving on:

   ```
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/andon_core.py validate-doc \
     '{"type":"gap","title":"...","stage":"...","kind":"...","status":"open","blast_radius":"<tag>","proposal":{}}'
   ```

   If this exits non-zero, your tag (or another gating field) is wrong --
   fix it before presenting the proposal, don't present a proposal you know
   will be rejected at write time.

## Phase 2: grill only what Phase 1 left load-bearing

Use the blast-radius tag from Phase 1 to decide whether to grill at all:

- `local+reversible`: **never grill.** You already decided in Phase 1;
  present the proposal as done.
- `hard-to-reverse` or `shared-state-visible`: **always** require explicit
  confirmation before the fix is applied. This is not a style preference --
  `andon-loop`'s stop-condition check will independently block advance on
  these tags until the user confirms, so skipping the grill here just moves
  the same halt one step later with less context for the user.

When grilling is required, ask about residual forks only -- the places where
Phase 1's draft genuinely could have gone two ways and the choice matters.
One question per turn:

1. State the fork plainly.
2. Give your recommended answer and the one-sentence reason for it.
3. Wait for the user's answer before asking the next question.

Do not batch multiple questions into one message, and do not ask about
anything Phase 1 already settled from the house-rules file or an unambiguous
codebase convention.

## Output

Return (never write to the ledger yourself -- `andon-loop` persists this):

```json
{
  "fix_description": "...",
  "files_touched": ["..."],
  "verify_strategy": "a",
  "verify_strategy_rationale": "...",
  "blast_radius": "hard-to-reverse"
}
```

